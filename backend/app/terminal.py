import asyncio
import os
import sys
import logging
import json

logger = logging.getLogger("devpilot.terminal")


class TerminalManager:
    """
    PTY-based terminal manager that provides a real terminal experience.
    Uses pywinpty (ConPTY) on Windows and the pty module on Unix/macOS.
    """

    def __init__(self, workspace_root: str, send_callback):
        self.workspace_root = workspace_root
        self.send_callback = send_callback  # async function to send data to websocket
        self._pty = None          # winpty.PtyProcess (Windows) or fd (Unix)
        self._process = None      # subprocess.Popen (Unix only)
        self._read_task = None
        self._cols = 120
        self._rows = 30

    async def start(self, cols: int = 120, rows: int = 30):
        """
        Starts a PTY-attached shell process and begins reading its output.
        """
        self._cols = cols
        self._rows = rows
        cwd = self.workspace_root if self.workspace_root and os.path.isdir(self.workspace_root) else os.path.expanduser("~")

        try:
            if sys.platform == "win32":
                await self._start_windows(cwd)
            else:
                await self._start_unix(cwd)
        except Exception as e:
            logger.error(f"Failed to start terminal: {e}")
            await self.send_callback(f"\r\nFailed to start terminal shell: {str(e)}\r\n")

    async def _start_windows(self, cwd: str):
        """Start a ConPTY-backed PowerShell process using pywinpty."""
        from winpty import PtyProcess

        shell_cmd = self._get_shell_command()

        # PtyProcess.spawn creates a ConPTY pseudoconsole — the same API
        # that VS Code's terminal uses under the hood.
        self._pty = PtyProcess.spawn(
            shell_cmd,
            cwd=cwd,
            dimensions=(self._rows, self._cols),
            env=os.environ.copy(),
        )

        # Start the async reader loop
        self._read_task = asyncio.create_task(self._read_loop_windows())

    async def _start_unix(self, cwd: str):
        """Start a PTY-backed shell process using the pty module (Unix/macOS)."""
        import pty
        import subprocess
        import struct
        import fcntl
        import termios

        shell_path = os.environ.get("SHELL") or "/bin/bash"

        # Create a PTY pair
        master_fd, slave_fd = pty.openpty()

        # Set the terminal size on the slave
        winsize = struct.pack("HHHH", self._rows, self._cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        # Spawn the shell with the slave as its controlling terminal
        self._process = subprocess.Popen(
            [shell_path, "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=cwd,
            env=os.environ.copy(),
            preexec_fn=os.setsid,
            close_fds=True,
        )

        # Close slave fd in the parent — we only need the master side
        os.close(slave_fd)

        # Store the master fd for reading/writing
        self._pty = master_fd

        # Make the master fd non-blocking for async reading
        import fcntl
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        self._read_task = asyncio.create_task(self._read_loop_unix())

    def _get_shell_command(self) -> str:
        """Get the shell command string for winpty."""
        if sys.platform == "win32":
            # Try to find powershell, fall back to cmd
            ps_path = os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
            )
            if os.path.isfile(ps_path):
                return ps_path
            return "cmd.exe"
        return os.environ.get("SHELL") or "/bin/bash"

    async def _read_loop_windows(self):
        """Read output from the ConPTY and forward to the WebSocket."""
        loop = asyncio.get_event_loop()
        try:
            while self._pty is not None and self._pty.isalive():
                try:
                    # Read from PTY in a thread executor to avoid blocking the event loop
                    data = await loop.run_in_executor(None, self._pty_read_windows)
                    if data:
                        await self.send_callback(data)
                except EOFError:
                    break
                except Exception as e:
                    if self._pty is None or not self._pty.isalive():
                        break
                    logger.debug(f"PTY read error (may be normal): {e}")
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Terminal read loop error: {e}")
        finally:
            await self.send_callback("\r\nTerminal shell exited.\r\n")

    def _pty_read_windows(self) -> str:
        """Blocking read from winpty — called in executor thread."""
        try:
            return self._pty.read(4096)
        except EOFError:
            raise
        except Exception:
            # Small sleep to prevent busy-spin on transient errors
            import time
            time.sleep(0.01)
            return ""

    async def _read_loop_unix(self):
        """Read output from the Unix PTY master fd and forward to the WebSocket."""
        loop = asyncio.get_event_loop()
        try:
            while self._pty is not None:
                try:
                    data = await loop.run_in_executor(None, self._pty_read_unix)
                    if data:
                        await self.send_callback(data)
                    elif data is None:
                        # EOF
                        break
                except OSError:
                    break
                except Exception as e:
                    if self._pty is None:
                        break
                    logger.debug(f"PTY read error: {e}")
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Terminal read loop error: {e}")
        finally:
            await self.send_callback("\r\nTerminal shell exited.\r\n")

    def _pty_read_unix(self) -> str | None:
        """Blocking read from Unix PTY — called in executor thread."""
        import select
        try:
            # Wait up to 0.1s for data
            ready, _, _ = select.select([self._pty], [], [], 0.1)
            if ready:
                data = os.read(self._pty, 4096)
                if not data:
                    return None  # EOF
                return data.decode("utf-8", errors="replace")
            return ""  # No data yet, just loop
        except OSError:
            return None

    async def write(self, data: str):
        """
        Writes raw input data to the PTY.
        The PTY handles echoing, line editing, etc. — no manual processing needed.
        """
        if self._pty is None:
            return

        try:
            if sys.platform == "win32":
                # winpty PtyProcess.write() accepts a string
                self._pty.write(data)
            else:
                # Unix: write raw bytes to the master fd
                os.write(self._pty, data.encode("utf-8"))
        except Exception as e:
            logger.error(f"Terminal write error: {e}")

    async def resize(self, cols: int, rows: int):
        """
        Notify the PTY of a terminal size change so the shell can reflow text.
        """
        self._cols = cols
        self._rows = rows

        if self._pty is None:
            return

        try:
            if sys.platform == "win32":
                # winpty PtyProcess.setwinsize(rows, cols)
                self._pty.setwinsize(rows, cols)
            else:
                import struct
                import fcntl
                import termios
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._pty, termios.TIOCSWINSZ, winsize)
        except Exception as e:
            logger.debug(f"Terminal resize error: {e}")

    async def stop(self):
        """
        Terminates the PTY process and cleans up.
        """
        # Cancel the reader task
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        # Clean up the PTY / process
        if sys.platform == "win32":
            if self._pty is not None:
                try:
                    if self._pty.isalive():
                        self._pty.terminate()
                except Exception:
                    pass
                self._pty = None
        else:
            # Unix: close master fd and terminate the process
            if self._pty is not None:
                try:
                    os.close(self._pty)
                except Exception:
                    pass
                self._pty = None

            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=1.0)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                self._process = None