block_cipher = None

a = Analysis(
    ['labelTrack/__main__.py'],
    pathex=['labelTrack'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher)

exe = EXE(
    pyz,
    Tree('icon',prefix='icon'),
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='labelTrack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False)
