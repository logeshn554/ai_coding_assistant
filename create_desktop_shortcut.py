import os
import sys
import subprocess

def create_desktop_shortcut(target_exe_or_bat=None, icon_path=None):
    project_root = os.path.dirname(os.path.abspath(__file__))
    dist_exe = os.path.join(project_root, "dist", "Loopix", "Loopix.exe")
    bat_file = os.path.join(project_root, "Loopix.bat")

    if target_exe_or_bat and os.path.exists(target_exe_or_bat):
        target = target_exe_or_bat
    elif os.path.exists(dist_exe):
        target = dist_exe
    elif os.path.exists(os.path.join(project_root, "dist", "Loopix", "Loopix.exe")):
        target = os.path.join(project_root, "dist", "Loopix", "Loopix.exe")
    elif os.path.exists(os.path.join(project_root, "Loopix.bat")):
        target = os.path.join(project_root, "Loopix.bat")
    else:
        target = bat_file

    if not icon_path:
        icon_path = os.path.join(project_root, "assets", "loopix.ico")

    ps_script = f"""
$Desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
if (-not (Test-Path $Desktop)) {{
    $Desktop = Join-Path $env:USERPROFILE "Desktop"
}}
$ShortcutPath = Join-Path $Desktop "Loopix AI Editor.lnk"
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "{target.replace('\\', '\\\\')}"
$Shortcut.WorkingDirectory = "{project_root.replace('\\', '\\\\')}"
$Shortcut.Description = "Loopix AI Coding Assistant & Code Editor"
if (Test-Path "{icon_path.replace('\\', '\\\\')}") {{
    $Shortcut.IconLocation = "{icon_path.replace('\\', '\\\\')},0"
}}
$Shortcut.Save()
Write-Host "Created shortcut at $ShortcutPath"
"""
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, check=True)
        print("Desktop shortcut created successfully!")
        print("Output:", res.stdout.strip())
        return True
    except Exception as e:
        print(f"Failed to create desktop shortcut: {e}")
        return False

if __name__ == "__main__":
    create_desktop_shortcut()
