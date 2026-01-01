# Upgrade to PANDA.1 v0.2.11 (Production)

## What's New

### 🔧 Code Quality Improvements
- Fixed all bare except clauses (better error handling)
- Replaced print() with proper logging
- Enhanced error messages with context
- Improved exception handling throughout

### 🐛 Bug Fixes
- Fixed resource management issues
- Improved error recovery
- Better exception propagation

### ⚡ Performance
- Removed duplicate imports
- Optimized code structure
- Better resource cleanup

## Upgrade Steps

1. **Backup your current installation**:
   ```bash
   cp -r ~/.panda1 ~/.panda1.backup
   ```

2. **Stop PANDA.1**:
   ```bash
   pkill -f "python.*panda"
   ```

3. **Install new version**:
   ```bash
   cd /path/to/panda1-production
   chmod +x install.sh
   ./install.sh
   ```

4. **Verify installation**:
   ```bash
   panda --status
   panda --voice-doctor
   ```

5. **Test functionality**:
   - GUI: `panda`
   - Voice: Test PTT and TTS
   - Agents: Check SCOTT/PENNY/SENSEI connections

## Configuration Changes

No configuration changes required. All existing `.env` settings are compatible.

## Rollback

If you need to rollback:
```bash
mv ~/.panda1 ~/.panda1.v0.2.11
mv ~/.panda1.backup ~/.panda1
```

## Notes

- All changes are backward compatible
- No database migrations needed
- Configuration files unchanged
- Works with existing SCOTT/PENNY/SENSEI agents

---

For issues, check logs at `~/.panda1/data/logs/`
