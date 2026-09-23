; ---------------------------------------------------------------------------
; Ad Blogs Bypass — instalador do componente local (companion) para
; navegadores Chromium (Inno Setup 6).
;
; O que ele faz:
;   1. copia a pasta do snet-bypass-companion.exe (saída do PyInstaller
;      --onedir: o exe + _internal\ com o Python e o driver do Playwright) para a
;      pasta de instalação;
;   2. gera o host manifest do Native Messaging apontando para o exe instalado
;      (o caminho só é conhecido na hora da instalação — por isso não é possível
;      distribuir o .json pronto);
;   3. registra o host em NativeMessagingHosts de TODOS os navegadores
;      Chromium conhecidos (Chrome, Edge, Brave, Vivaldi, Opera, Chromium) e dos
;      canais Beta/Dev/Canary/Nightly, que usam chave própria;
;   4. cria a entrada em "Aplicativos e recursos".
;
; Ao desinstalar, tudo isso é desfeito: arquivos, o .json gerado, as chaves do
; host e — se ficarem vazias — as chaves-pai criadas aqui.
;
; POR QUE REGISTRAR TODOS SEM PERGUNTAR: a chave de um navegador que não está
; instalado é um valor de registro inerte, que o desinstalador remove junto.
; Deixar o usuário escolher cria um modo de falha real — instalar marcando só
; um navegador e a extensão responder "Specified native messaging host not
; found". Detectar o que está instalado também não ajudaria: quem instala o
; navegador depois do companion ficaria sem registro, sem pista do motivo.
;
; O allowed_origins do manifest usa o ID FIXO da extensão, que vem do campo
; "key" do extension\manifest.json. Se aquele campo mudar, este ID muda junto e
; o Chromium passa a recusar a conexão com "Access to the specified native
; messaging host is forbidden". O build-installer.ps1 e o
; tests\test_companion.py conferem os dois.
;
; Compilar: .\build-installer.ps1 (gera o exe antes, se preciso).
; ---------------------------------------------------------------------------

#define AppName       "Ad Blogs Bypass Companion"
; GUID próprio deste instalador: não pode colidir com o de outro programa,
; senão um desinstala o outro.
#define AppIdGuid     "{77DF8D0F-98F9-418E-932F-4DDEB2112B6E}"
; o build-installer.ps1 passa a versão do extension\manifest.json via
; /DAppVersion=...; este valor é só o valor de reserva para quem compilar direto no IDE.
#ifndef AppVersion
  #define AppVersion  "2.0.0"
#endif
#define AppPublisher  "Ad Blogs Bypass"
#define HostName      "com.corrente.host"
#define ExtensionId   "gdffnebealemedjembikfbagoijgmeij"
#define HostManifest  "host-manifest.json"
#define ExeName       "snet-bypass-companion.exe"

; Fonte (este .iss vive em installer\, um nível abaixo da raiz).
#define CompanionDir  "..\companion\dist\snet-bypass-companion"

#if !FileExists(AddBackslash(SourcePath) + CompanionDir + "\" + ExeName)
  #error snet-bypass-companion.exe nao encontrado. Rode companion\build.ps1 (ou installer\build-installer.ps1) antes de compilar.
#endif

[Setup]
AppId={{#AppIdGuid}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Ad Blogs Bypass Companion
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=ad-blogs-bypass-companion-{#AppVersion}-setup
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

; Instalação por usuário por padrão (sem UAC, chaves em HKCU). O usuário pode
; escolher "para todos" na primeira tela — nesse caso a instalação vai para Program Files + HKLM.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline

; O exe é gerado pelo Python x64: só faz sentido em 64 bits. Rodar o setup em
; modo 64 bits também evita a redireção para o Wow6432Node — se a chave caísse lá,
; o navegador de 64 bits simplesmente não acharia o host.
; (x64compatible só existe do Inno 6.3 em diante; antes disso o nome era x64.)
#if VER >= EncodeVer(6,3,0,0)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#else
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
; A pasta inteira: o exe depende do _internal\ ao lado dele.
Source: "{#CompanionDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
; HKA = HKLM na instalação para todos, HKCU na instalação por usuário.
;
; ORDEM IMPORTA: o desinstalador lê o log de trás para a frente, então as entradas
; são desfeitas na ordem inversa. As chaves-pai vêm primeiro justamente para
; serem testadas por último — quando a chave do host já foi removida e elas
; realmente estão vazias. Na ordem contrária, sobrariam todas.
;
; uninsdeletekeyifempty nunca leva junto nada que não seja nosso: se a chave
; tiver qualquer valor ou subchave de outro programa, ela fica. É o que torna
; seguro criar a chave dos seis navegadores sem perguntar: as de quem não está
; instalado ficam vazias e somem na desinstalação.

; --- Chrome ---
Root: HKA; Subkey: "Software\Google"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Google\Chrome"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Google\Chrome\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Google\Chrome\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

; --- Edge ---
Root: HKA; Subkey: "Software\Microsoft\Edge"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

; --- Brave ---
Root: HKA; Subkey: "Software\BraveSoftware"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

; --- Vivaldi ---
Root: HKA; Subkey: "Software\Vivaldi"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Vivaldi\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Vivaldi\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

; --- Opera ---
Root: HKA; Subkey: "Software\Opera Software"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Opera Software\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Opera Software\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

; --- Chromium ---
Root: HKA; Subkey: "Software\Chromium"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Chromium\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Chromium\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

; --- Canais Beta/Dev/Canary/Nightly (chave própria; inertes se o canal não existir) ---
Root: HKA; Subkey: "Software\Google\Chrome SxS"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Google\Chrome SxS\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Google\Chrome SxS\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Edge Beta"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge Beta\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge Beta\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Edge Dev"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge Dev\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge Dev\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Edge SxS"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge SxS\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\Microsoft\Edge SxS\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Beta"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Beta\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Beta\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Nightly"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Nightly\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Nightly\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Dev"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Dev\NativeMessagingHosts"; Flags: uninsdeletekeyifempty
Root: HKA; Subkey: "Software\BraveSoftware\Brave-Browser-Dev\NativeMessagingHosts\{#HostName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#HostManifest}"; Flags: uninsdeletekey

[UninstallDelete]
; Gerado em tempo de instalação (não veio no [Files], então some aqui).
Type: files; Name: "{app}\{#HostManifest}"
Type: dirifempty; Name: "{app}"

[Code]

{ ------------------------------------------------------------------ }
{ Tabela dos navegadores, usada só pela varredura de registros conflitantes —
  a criação das chaves é declarativa, na seção [Registry] acima. }
function NumNavegadores: Integer;
begin
  Result := 13;
end;

function NomeDe(I: Integer): String;
begin
  case I of
    0: Result := 'Google Chrome';
    1: Result := 'Microsoft Edge';
    2: Result := 'Brave';
    3: Result := 'Vivaldi';
    4: Result := 'Opera';
    5: Result := 'Chromium';
    6: Result := 'Chrome Canary';
    7: Result := 'Edge Beta';
    8: Result := 'Edge Dev';
    9: Result := 'Edge Canary';
    10: Result := 'Brave Beta';
    11: Result := 'Brave Nightly';
  else Result := 'Brave Dev';
  end;
end;

{ Chave COMPLETA do host (já com o nome do host no fim). }
function ChaveDe(I: Integer): String;
begin
  case I of
    0: Result := 'Software\Google\Chrome\NativeMessagingHosts\{#HostName}';
    1: Result := 'Software\Microsoft\Edge\NativeMessagingHosts\{#HostName}';
    2: Result := 'Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\{#HostName}';
    3: Result := 'Software\Vivaldi\NativeMessagingHosts\{#HostName}';
    4: Result := 'Software\Opera Software\NativeMessagingHosts\{#HostName}';
    5: Result := 'Software\Chromium\NativeMessagingHosts\{#HostName}';
    6: Result := 'Software\Google\Chrome SxS\NativeMessagingHosts\{#HostName}';
    7: Result := 'Software\Microsoft\Edge Beta\NativeMessagingHosts\{#HostName}';
    8: Result := 'Software\Microsoft\Edge Dev\NativeMessagingHosts\{#HostName}';
    9: Result := 'Software\Microsoft\Edge SxS\NativeMessagingHosts\{#HostName}';
    10: Result := 'Software\BraveSoftware\Brave-Browser-Beta\NativeMessagingHosts\{#HostName}';
    11: Result := 'Software\BraveSoftware\Brave-Browser-Nightly\NativeMessagingHosts\{#HostName}';
  else Result := 'Software\BraveSoftware\Brave-Browser-Dev\NativeMessagingHosts\{#HostName}';
  end;
end;

{ ------------------------------------------------------------------ }
{ O exe (e o _internal\) fica bloqueado enquanto está rodando. Sobrescrever ou
  apagar nesse estado falha (ou fica para depois de reiniciar), então checamos antes e
  pedimos ao usuário que feche o navegador.

  É raro: o navegador abre um processo por link capturado, e ele sai sozinho
  assim que responde. }
function CompanionRunning: Boolean;
var
  Rc: Integer;
begin
  Result := False;
  if Exec(ExpandConstant('{cmd}'),
          '/C tasklist /FI "IMAGENAME eq {#ExeName}" /NH | find /I "{#ExeName}" >nul',
          '', SW_HIDE, ewWaitUntilTerminated, Rc) then
    Result := (Rc = 0);
end;

function AskToClose(const Acao: String): Boolean;
begin
  Result := True;
  while CompanionRunning do
  begin
    if MsgBox('O componente do Ad Blogs Bypass está em execução.'#13#10#13#10
              + 'Feche o Brave (ou aguarde a conclusão dos links em andamento) e clique em Repetir para continuar '
              + Acao + '.',
              mbConfirmation, MB_RETRYCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
  end;
end;

{ ------------------------------------------------------------------ }
function Hex4(C: Integer): String;
var
  D: String;
begin
  D := '0123456789abcdef';
  Result := D[((C shr 12) and 15) + 1] + D[((C shr 8) and 15) + 1]
          + D[((C shr 4) and 15) + 1] + D[(C and 15) + 1];
end;

{ Escapa a string para o JSON e, além disso, mantém o arquivo em ASCII puro
  (qualquer caractere acima de 126 vira \uXXXX). Isso é necessário: o
  SaveStringToFile grava em ANSI, então um caminho com acento — "C:\Users\Usuário\..."
  na instalação por usuário — sairia em CP1252 e o navegador, que espera UTF-8,
  falharia em ler o manifest sem dizer o motivo. }
function JsonEscape(const S: String): String;
var
  I, C: Integer;
begin
  Result := '';
  for I := 1 to Length(S) do
  begin
    C := Ord(S[I]);
    if S[I] = '\' then Result := Result + '\\'
    else if S[I] = '"' then Result := Result + '\"'
    else if (C < 32) or (C > 126) then Result := Result + '\u' + Hex4(C)
    else Result := Result + S[I];
  end;
end;

{ O host manifest precisa do caminho ABSOLUTO do exe. Como esse caminho só
  existe depois que o usuário escolhe a pasta, o arquivo é escrito aqui em vez
  de ser distribuído pronto. "allowed_origins" leva a origem
  chrome-extension://<id>/, barra no fim inclusive. }
procedure WriteHostManifest;
var
  Json, Destino: String;
begin
  Destino := ExpandConstant('{app}\{#HostManifest}');
  Json :=
    '{'#13#10 +
    '  "name": "{#HostName}",'#13#10 +
    '  "description": "Ad Blogs Bypass - componente local",'#13#10 +
    '  "path": "' + JsonEscape(ExpandConstant('{app}\{#ExeName}')) + '",'#13#10 +
    '  "type": "stdio",'#13#10 +
    '  "allowed_origins": ["chrome-extension://{#ExtensionId}/"]'#13#10 +
    '}'#13#10;

  { Sem RaiseException: aqui os arquivos e o desinstalador já foram gravados, e
    abortar deixaria a instalação pela metade (entrada em Adicionar/Remover
    apontando para um manifesto inexistente). Melhor concluir e avisar. }
  if not SaveStringToFile(Destino, Json, False) then
    MsgBox('Não foi possível gravar o arquivo de configuração em:'#13#10 + Destino + #13#10#13#10
           + 'A extensão não encontrará o componente enquanto isso não for resolvido. '
           + 'Instale novamente em uma pasta com permissão de escrita.',
           mbError, MB_OK);
end;

{ Um registro por usuário apontando para outro lugar tem prioridade e faria o
  navegador continuar abrindo o exe antigo depois desta instalação.
  Varre todos os navegadores/canais registrados.

  Limitação conhecida: se a elevação for feita com a conta de OUTRO usuário
  (credencial de admin digitada por cima), o HKCU lido aqui é o do admin, e um
  registro antigo do usuário logado passa despercebido. Não há como acessar o
  HKCU do usuário original pelo Inno — nesse caso, rodar o instalador de novo
  em modo "só para mim" resolve. }
procedure LimparRegistroConflitante;
var
  I: Integer;
  Existente, Nosso, Antigos: String;
begin
  Nosso := ExpandConstant('{app}\{#HostManifest}');
  Antigos := '';

  for I := 0 to NumNavegadores - 1 do
  begin
    if IsAdminInstallMode then
    begin
      if RegQueryStringValue(HKCU, ChaveDe(I), '', Existente) and (CompareText(Existente, Nosso) <> 0) then
      begin
        if MsgBox('Existe uma instalação anterior do componente, apenas para o seu usuário, no ' + NomeDe(I) + ', que aponta para:'#13#10#13#10
                  + Existente + #13#10#13#10
                  + 'Ela tem prioridade sobre esta instalação e faria o navegador continuar usando o componente antigo. Deseja removê-la?',
                  mbConfirmation, MB_YESNO) = IDYES then
          RegDeleteKeyIncludingSubkeys(HKCU, ChaveDe(I));
      end;
    end
    else
    begin
      if RegQueryStringValue(HKLM, ChaveDe(I), '', Existente) and (CompareText(Existente, Nosso) <> 0) then
        Antigos := Antigos + '  - ' + NomeDe(I) + ': ' + Existente + #13#10;
    end;
  end;

  if Antigos <> '' then
    MsgBox('Aviso: existe uma instalação do componente para todos os usuários que aponta para outro local:'#13#10#13#10
           + Antigos + #13#10
           + 'Esta instalação (apenas para você) tem prioridade. Caso algo não funcione como esperado, '
           + 'desinstale a versão para todos os usuários em "Aplicativos e recursos".',
           mbInformation, MB_OK);
end;

{ ------------------------------------------------------------------ }
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not AskToClose('a instalação') then
    Result := 'Instalação cancelada: o componente estava em execução.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteHostManifest;
    LimparRegistroConflitante;
  end;
end;

function InitializeUninstall: Boolean;
begin
  Result := AskToClose('a desinstalação');
end;
