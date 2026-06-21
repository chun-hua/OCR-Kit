param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$computer = Get-CimInstance Win32_ComputerSystem
$gpus = Get-CimInstance Win32_VideoController |
    Where-Object { $_.Name -and $_.Name -notmatch 'Remote|Oray|Virtual' }

$gpuNames = @($gpus | ForEach-Object { $_.Name }) -join ' / '
$nvidia = @($gpus | Where-Object { $_.Name -match 'NVIDIA' }).Count -gt 0
$memoryGB = [math]::Round($computer.TotalPhysicalMemory / 1GB)

@(
    "CPUName=$($cpu.Name)"
    "LogicalProcessors=$($cpu.NumberOfLogicalProcessors)"
    "MemoryGB=$memoryGB"
    "GPUName=$gpuNames"
    "NVIDIA=$($nvidia.ToString().ToLowerInvariant())"
) | Set-Content -LiteralPath $OutputPath -Encoding UTF8
