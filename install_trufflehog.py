import os
import tarfile
import urllib.request

TRUFFLEHOG_VERSION = "3.88.10"
INSTALL_DIR = (
    os.path.expanduser("~/.trufflehog")
    if os.name != "nt"
    else os.path.expanduser("~\\trufflehog")
)
DOWNLOAD_URL = f"https://github.com/trufflesecurity/trufflehog/releases/download/v{TRUFFLEHOG_VERSION}/trufflehog_{TRUFFLEHOG_VERSION}_linux_amd64.tar.gz"
if os.name == "nt":
    DOWNLOAD_URL = f"https://github.com/trufflesecurity/trufflehog/releases/download/v{TRUFFLEHOG_VERSION}/trufflehog_{TRUFFLEHOG_VERSION}_windows_amd64.tar.gz"
TAR_FILE = os.path.join(INSTALL_DIR, "trufflehog.tar.gz")

# Ensure installation directory exists
os.makedirs(INSTALL_DIR, exist_ok=True)

# Detect correct binary name
EXECUTABLE = os.path.join(INSTALL_DIR, "trufflehog")
EXECUTABLE_WIN = os.path.join(INSTALL_DIR, "trufflehog.exe")

# Check if TruffleHog is installed and executable
if not (os.path.isfile(EXECUTABLE) or os.path.isfile(EXECUTABLE_WIN)):
    print(f"TruffleHog not found. Downloading version {TRUFFLEHOG_VERSION}...")

    # Download TruffleHog
    urllib.request.urlretrieve(DOWNLOAD_URL, TAR_FILE)

    with tarfile.open(TAR_FILE, "r:gz") as tar:
        tar.extractall(path=INSTALL_DIR)

    # Locate the correct binary and rename if needed
    extracted_files = os.listdir(INSTALL_DIR)
    for file in extracted_files:
        full_path = os.path.join(INSTALL_DIR, file)
        if os.path.isfile(full_path) and "trufflehog" in file and "tar.gz" not in file:
            if os.name == "nt" and not file.endswith(".exe"):
                os.rename(full_path, EXECUTABLE_WIN)
            elif os.name != "nt":
                os.rename(full_path, EXECUTABLE)
            break

    # Ensure executable permissions on Linux
    if os.name != "nt" and os.path.isfile(EXECUTABLE):
        os.chmod(EXECUTABLE, 0o755)

    # Remove the tar/zip file
    os.remove(TAR_FILE)

    print(
        f"TruffleHog installed successfully at {EXECUTABLE if os.name != 'nt' else EXECUTABLE_WIN}.",
    )
else:
    print(
        f"TruffleHog is already installed at {EXECUTABLE if os.name != 'nt' else EXECUTABLE_WIN}.",
    )

# Add TruffleHog to PATH permanently
if os.name == "nt":
    # Windows: Use setx to update the PATH
    current_path = os.environ["PATH"]
    if INSTALL_DIR not in current_path:
        os.system(f'setx PATH "{current_path};{INSTALL_DIR}"')
        print(
            f"Added {INSTALL_DIR} to Windows PATH. Restart your terminal to apply changes.",
        )
else:
    # Linux/macOS/WSL: Update ~/.bashrc
    bashrc_path = os.path.expanduser("~/.bashrc")
    with open(bashrc_path, "r") as bashrc:
        if f'export PATH="{INSTALL_DIR}:$PATH"' not in bashrc.read():
            with open(bashrc_path, "a") as bashrc:
                bashrc.write(f'\nexport PATH="{INSTALL_DIR}:$PATH"\n')
            print(
                f"Updated ~/.bashrc to include {INSTALL_DIR}. Run 'source ~/.bashrc' to apply changes.",
            )

print(f"Updated PATH to include {INSTALL_DIR}")
