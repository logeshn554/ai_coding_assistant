import asyncio
import os
import sys

class TerminalManager:
    def __init__(self, workspace_root: str, send_callback):
        self.workspace_root = workspace_root
        self.send_callback = send_callback  # async function to send data to websocket
        self.process = None
        self.read_task = None

    async def start(self):
        """
        Starts the persistent shell process (PowerShell on Windows, bash/sh on Unix)
        and begins reading its output.
        """
        shell = "powershell.exe" if sys.platform == "win32" else "bash"
        
        # On Windows, powershell.exe might run in non-interactive mode if it sees stdin redirected.
        # We run it with -NoLogo and pipe stdin, stdout, stderr.
        try:
            cwd_dir = self.workspace_root if self.workspace_root and os.path.isdir(self.workspace_root) else os.path.expanduser("~")
            self.process = await asyncio.create_subprocess_exec(
                shell,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, # pipe stderr to stdout to keep it in order
                cwd=cwd_dir,
                env=os.environ.copy()
            )
            # Start background reader task
            self.read_task = asyncio.create_task(self._read_output_loop())
            
            # Send an initial welcome message or newline to trigger prompt print
            await self.write("\r\n")
        except Exception as e:
            await self.send_callback(f"\r\nFailed to start terminal shell: {str(e)}\r\n")

    async def write(self, data: str):
        """
        Writes data (keystrokes, commands) to the shell's stdin.
        """
        if self.process and self.process.stdin:
            try:
                # xterm.js sends \r for enter, convert to \r\n for PowerShell if needed
                # However, powershell typically handles standard inputs correctly.
                self.process.stdin.write(data.encode("utf-8"))
                await self.process.stdin.drain()
            except Exception as e:
                await self.send_callback(f"\r\nTerminal input error: {str(e)}\r\n")

    async def _read_output_loop(self):
        """
        Reads output bytes from the shell and pushes them to the websocket callback.
        """
        try:
            while self.process and self.process.stdout:
                # Read chunks of bytes (e.g. up to 1024 bytes)
                # We read at least 1 byte, blocking until data is available.
                data = await self.process.stdout.read(1024)
                if not data:
                    break
                # Send raw string/bytes back to frontend. xterm.js handles raw bytes
                # or utf-8 strings. We decode with errors='replace' to avoid crashes.
                await self.send_callback(data.decode("utf-8", errors="replace"))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.send_callback(f"\r\nTerminal connection read error: {str(e)}\r\n")
        finally:
            await self.send_callback("\r\nTerminal shell exited.\r\n")

    async def stop(self):
        """
        Terminates the process and cleans up tasks.
        """
        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
            self.read_task = None

        if self.process:
            try:
                self.process.terminate()
                # Wait briefly for termination
                await asyncio.wait_for(self.process.wait(), timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
