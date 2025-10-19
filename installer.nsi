; KotobaTranscriber Installer Script
; NSIS 3.x compatible

!include "MUI2.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"
!include "WinVer.nsh"

; 基本情報
Name "KotobaTranscriber"
OutFile "dist\KotobaTranscriber-installer.exe"
InstallDir "$PROGRAMFILES\KotobaTranscriber"
InstallDirRegKey HKCU "Software\KotobaTranscriber" "InstallLocation"

; 管理者権限要求
RequestExecutionLevel admin

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_WELCOMEFINISHPAGE_BITMAP "wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "wizard.bmp"
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; Language
!insertmacro MUI_LANGUAGE "Japanese"
!insertmacro MUI_LANGUAGE "English"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; インストール処理
Section "Install"
  SetOutPath "$INSTDIR"

  ; 実行ファイルをコピー
  File /r "dist\KotobaTranscriber\*.*"

  ; スタートメニューショートカット作成
  CreateDirectory "$SMPROGRAMS\KotobaTranscriber"
  CreateShortCut "$SMPROGRAMS\KotobaTranscriber\KotobaTranscriber.lnk" "$INSTDIR\KotobaTranscriber.exe" "" "$INSTDIR\KotobaTranscriber.exe" 0
  CreateShortCut "$SMPROGRAMS\KotobaTranscriber\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0

  ; デスクトップショートカット作成
  CreateShortCut "$DESKTOP\KotobaTranscriber.lnk" "$INSTDIR\KotobaTranscriber.exe" "" "$INSTDIR\KotobaTranscriber.exe" 0

  ; アンインストーラー作成
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; レジストリにインストール情報を登録
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "DisplayName" "KotobaTranscriber - Japanese Speech-to-Text"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "DisplayVersion" "2.1.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "Publisher" "KotobaTranscriber Team"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "URLInfoAbout" "https://github.com/yourusername/KotobaTranscriber"

  ; インストールサイズを取得して登録
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWord HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber" "EstimatedSize" "$0"

  WriteRegStr HKCU "Software\KotobaTranscriber" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\KotobaTranscriber" "Version" "2.1.0"

  ; ファイアウォール例外追加（オプション）
  ; DetailPrint "Adding Windows Firewall exception..."
  ; ExecWait 'netsh advfirewall firewall add rule name="KotobaTranscriber" dir=in action=allow program="$INSTDIR\KotobaTranscriber.exe" enable=yes'

  SetOutPath "$INSTDIR"
  DetailPrint "Installation Complete!"
SectionEnd

; アンインストール処理
Section "Uninstall"
  ; アプリケーションが実行中の場合は終了
  FindWindow $0 "KotobaTranscriber" ""
  ${If} $0 != 0
    MessageBox MB_OKCANCEL "KotobaTranscriberは実行中です。終了してからアンインストールを続行してください。" IDOK uninst_continue IDCANCEL uninst_abort
    uninst_abort:
      Quit
    uninst_continue:
  ${EndIf}

  ; ショートカット削除
  RMDir /r "$SMPROGRAMS\KotobaTranscriber"
  Delete "$DESKTOP\KotobaTranscriber.lnk"

  ; ファイル削除
  RMDir /r "$INSTDIR"

  ; レジストリエントリ削除
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\KotobaTranscriber"
  DeleteRegKey HKCU "Software\KotobaTranscriber"

  DetailPrint "Uninstallation Complete!"
SectionEnd

; 言語文字列の定義
LangString DESC_Install ${LANG_JAPANESE} "KotobaTranscriberをインストールします"
LangString DESC_Install ${LANG_ENGLISH} "Install KotobaTranscriber"
