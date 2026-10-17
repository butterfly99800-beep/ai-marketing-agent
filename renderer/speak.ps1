param([string]$TextFile,[string]$OutputFile,[int]$Rate=1)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$v=New-Object System.Speech.Synthesis.SpeechSynthesizer
$t=[IO.File]::ReadAllText($TextFile)
if($t -match '[\u4e00-\u9fff]'){$v.SelectVoice('Microsoft Huihui Desktop')}else{$v.SelectVoice('Microsoft Zira Desktop')}
$v.Rate=[Math]::Max(-2,[Math]::Min(6,$Rate))
$v.SetOutputToWaveFile($OutputFile)
$v.Speak($t)
$v.Dispose()
