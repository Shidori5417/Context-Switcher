import subprocess

def run():
    result = subprocess.run([r".venv\Scripts\pytest.exe", "tests/test_tray.py", "tests/test_hotkeys.py", "--tb=short"], capture_output=True, text=True)
    with open("test_results.log", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        f.write("\nSTDERR:\n")
        f.write(result.stderr)
        
if __name__ == "__main__":
    run()
