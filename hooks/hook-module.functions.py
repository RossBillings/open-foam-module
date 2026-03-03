from PyInstaller.utils.hooks import collect_submodules

ISTARI_FUNCTIONS_PACKAGE = "module.functions"
ISTARI_FUNCTIONS_BASE = "module.functions.base"


hiddenimports = collect_submodules(
    ISTARI_FUNCTIONS_PACKAGE,
    filter=lambda name: ISTARI_FUNCTIONS_BASE not in name,
)
