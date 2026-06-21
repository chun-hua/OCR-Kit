#ifndef Variant
  #define Variant "cpu"
#endif

#if Variant == "cuda"
  #define IsCudaBuild "True"
#else
  #define IsCudaBuild "False"
#endif

#define AppName "OCR-Kit"
#define AppVersion "1.0.0"
#define AppPublisher "OCR-Kit"
#define AppExeName "OCR-Kit.exe"

[Setup]
AppId={{C9CFB53F-647B-4E87-A76D-6D31B23D6118}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=OCR-Kit-{#AppVersion}-windows-{#Variant}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
SetupLogging=yes

[Files]
Source: "..\dist\{#Variant}\OCR-Kit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "hardware_probe.ps1"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\OCR-Kit"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\OCR-Kit"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 OCR-Kit"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\OCR-Kit"; ValueType: string; ValueName: "ConfigPath"; ValueData: "{userappdata}\OCR-Kit\config.json"; Flags: uninsdeletekey

[Code]
var
  StoragePage: TInputDirWizardPage;
  PerfPage: TInputOptionWizardPage;
  HardwareLabel: TNewStaticText;
  CPUName, GPUName: String;
  LogicalProcessors, MemoryGB: Integer;
  HasNVIDIA: Boolean;

function ReadProbeValue(const FileName, Key: String): String;
var
  Lines: TArrayOfString;
  I: Integer;
  Prefix: String;
begin
  Result := '';
  Prefix := Key + '=';
  if LoadStringsFromFile(FileName, Lines) then
    for I := 0 to GetArrayLength(Lines) - 1 do
      if Pos(Prefix, Lines[I]) = 1 then
      begin
        Result := Copy(Lines[I], Length(Prefix) + 1, MaxInt);
        Exit;
      end;
end;

procedure DetectHardware;
var
  ResultCode: Integer;
  ProbeScript, ProbeOutput, Args: String;
begin
  CPUName := '未检测到';
  GPUName := '未检测到独立显卡';
  LogicalProcessors := 1;
  MemoryGB := 0;
  HasNVIDIA := False;

  ExtractTemporaryFile('hardware_probe.ps1');
  ProbeScript := ExpandConstant('{tmp}\hardware_probe.ps1');
  ProbeOutput := ExpandConstant('{tmp}\ocr-kit-hardware.txt');
  Args := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ProbeScript + '" -OutputPath "' + ProbeOutput + '"';

  if Exec('powershell.exe', Args, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and
     (ResultCode = 0) then
  begin
    CPUName := ReadProbeValue(ProbeOutput, 'CPUName');
    GPUName := ReadProbeValue(ProbeOutput, 'GPUName');
    LogicalProcessors := StrToIntDef(ReadProbeValue(ProbeOutput, 'LogicalProcessors'), 1);
    MemoryGB := StrToIntDef(ReadProbeValue(ProbeOutput, 'MemoryGB'), 0);
    HasNVIDIA := CompareText(ReadProbeValue(ProbeOutput, 'NVIDIA'), 'true') = 0;
  end;
end;

function RecommendedProfileIndex: Integer;
begin
  if {#IsCudaBuild} and HasNVIDIA and (MemoryGB >= 8) then
    Result := 3
  else if (MemoryGB >= 16) and (LogicalProcessors >= 8) then
    Result := 2
  else if (MemoryGB > 0) and (MemoryGB < 8) then
    Result := 0
  else
    Result := 1;
end;

function ProfileName(Index: Integer): String;
begin
  case Index of
    0: Result := 'compatible';
    1: Result := 'balanced';
    2: Result := 'performance';
    3: Result := 'cuda';
  end;
end;

function ProfileModel(Index: Integer): String;
begin
  case Index of
    0: Result := 'tiny';
    1: Result := 'small';
  else
    Result := 'medium';
  end;
end;

function ProfileThreads(Index: Integer): Integer;
begin
  case Index of
    0: Result := 2;
    1:
      begin
        Result := LogicalProcessors;
        if Result > 6 then Result := 6;
        if Result < 2 then Result := 2;
      end;
    2:
      begin
        Result := LogicalProcessors;
        if Result > 12 then Result := 12;
        if Result < 4 then Result := 4;
      end;
    3: Result := 4;
  end;
end;

function JsonEscape(Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure InitializeWizard;
var
  Recommended: Integer;
begin
  DetectHardware;

  StoragePage := CreateInputDirPage(
    wpSelectDir,
    '选择模型和项目数据目录',
    '模型与项目数据独立于程序安装目录',
    '请选择模型缓存和项目数据的存放位置。后续升级或卸载程序时不会自动删除这些数据。',
    False,
    '新建文件夹'
  );
  StoragePage.Add('模型存放目录：');
  StoragePage.Add('项目数据目录：');
  StoragePage.Values[0] := ExpandConstant('{localappdata}\OCR-Kit\models');
  StoragePage.Values[1] := ExpandConstant('{userdocs}\OCR-Kit');

  PerfPage := CreateInputOptionPage(
    StoragePage.ID,
    '硬件与性能配置建议',
    '安装程序已检测当前电脑，并给出建议配置',
    '选择一个初始运行档位。所有配置安装后仍可在程序右上角的设置中修改。',
    True,
    False
  );
  PerfPage.Add('兼容模式 — 4–8 GB 内存、2–4 核 CPU；Tiny 模型，低占用');
  PerfPage.Add('均衡模式 — 8 GB+ 内存、4 核+ CPU；Small 模型，适合多数电脑');
  PerfPage.Add('高性能 CPU — 16 GB+ 内存、8 核+ CPU；Medium 模型，优先精度');
  PerfPage.Add('NVIDIA CUDA — NVIDIA 显卡、8 GB+ 内存；需要 CUDA 版安装包和兼容驱动');

  Recommended := RecommendedProfileIndex;
  PerfPage.SelectedValueIndex := Recommended;
  PerfPage.CheckListBox.ItemEnabled[3] := {#IsCudaBuild} and HasNVIDIA;

  HardwareLabel := TNewStaticText.Create(PerfPage);
  HardwareLabel.Parent := PerfPage.Surface;
  HardwareLabel.Left := 0;
  HardwareLabel.Top := ScaleY(198);
  HardwareLabel.Width := PerfPage.SurfaceWidth;
  HardwareLabel.Height := ScaleY(72);
  HardwareLabel.AutoSize := False;
  HardwareLabel.WordWrap := True;
  HardwareLabel.Caption :=
    '检测结果：' + CPUName + '；' + IntToStr(LogicalProcessors) + ' 个逻辑处理器；' +
    IntToStr(MemoryGB) + ' GB 内存；显卡：' + GPUName + #13#10 +
    '已自动选择建议项。注意：检测到显卡不等于 CUDA 运行环境可用，CPU 版安装包不会开放 GPU 选项。';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = StoragePage.ID then
  begin
    if (Trim(StoragePage.Values[0]) = '') or (Trim(StoragePage.Values[1]) = '') then
    begin
      MsgBox('模型目录和项目数据目录都不能为空。', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir, ConfigPath, ConfigJson, Device: String;
  ProfileIndex: Integer;
  ConfigLines: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(StoragePage.Values[0]);
    ForceDirectories(StoragePage.Values[1]);
    ConfigDir := ExpandConstant('{userappdata}\OCR-Kit');
    ConfigPath := ConfigDir + '\config.json';
    ForceDirectories(ConfigDir);

    ProfileIndex := PerfPage.SelectedValueIndex;
    if ProfileIndex = 3 then Device := 'gpu' else Device := 'cpu';

    ConfigJson :=
      '{' + #13#10 +
      '  "version": 1,' + #13#10 +
      '  "model_dir": "' + JsonEscape(StoragePage.Values[0]) + '",' + #13#10 +
      '  "project_dir": "' + JsonEscape(StoragePage.Values[1]) + '",' + #13#10 +
      '  "performance_profile": "' + ProfileName(ProfileIndex) + '",' + #13#10 +
      '  "device": "' + Device + '",' + #13#10 +
      '  "cpu_threads": ' + IntToStr(ProfileThreads(ProfileIndex)) + ',' + #13#10 +
      '  "ocr_workers": 1,' + #13#10 +
      '  "default_model": "' + ProfileModel(ProfileIndex) + '",' + #13#10 +
      '  "open_browser": true,' + #13#10 +
      '  "server_port": 8765' + #13#10 +
      '}' + #13#10;
    SetArrayLength(ConfigLines, 1);
    ConfigLines[0] := ConfigJson;
    SaveStringsToUTF8FileWithoutBOM(ConfigPath, ConfigLines, False);
  end;
end;
