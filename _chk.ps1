$t=$null;$e=$null
[System.Management.Automation.Language.Parser]::ParseFile('D:\my-blog\git_sync_realtime_GitAutoSync_myblog_6FFD71.ps1',[ref]$t,[ref]$e)|Out-Null
if($e.Count-eq 0){Write-Host "OK: syntax valid"}else{$e|ForEach-Object{Write-Host ($_.Extent.StartLineNumber.ToString()+': '+$_.Message)}}
