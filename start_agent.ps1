# Quick start script for the AI Coding Agent
# Windows PowerShell

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "🤖 AI CODING AGENT - STARTUP" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}
Write-Host "✓ $pythonVersion" -ForegroundColor Green

# Check API Key
Write-Host "Checking API key..." -ForegroundColor Yellow
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "❌ ANTHROPIC_API_KEY not set" -ForegroundColor Red
    Write-Host ""
    Write-Host "Set your API key with:" -ForegroundColor Yellow
    Write-Host '  $env:ANTHROPIC_API_KEY = "your-api-key-here"' -ForegroundColor White
    Write-Host ""
    Write-Host "Get your key from: https://console.anthropic.com/" -ForegroundColor Cyan
    exit 1
}
Write-Host "✓ API key found" -ForegroundColor Green

# Check dependencies
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$anthropicInstalled = pip show anthropic 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  anthropic package not found. Installing..." -ForegroundColor Yellow
    pip install -r requirements_agent.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
}
Write-Host "✓ Dependencies ready" -ForegroundColor Green

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "🚀 STARTING AGENT" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Run the agent
python coding_agent.py
