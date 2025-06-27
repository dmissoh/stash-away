# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python CLI tool called `stash-away` that helps developers back up their Git repositories to separate backup repositories or create local archives. The tool is designed to be compiled into a standalone executable using PyInstaller.

## Commands for Development

### Building the Executable
```bash
# Quick build using the provided script
./build.sh

# Or manually with PyInstaller
pyinstaller stash-away.spec

# The executable will be created in dist/stash-away
```

### Installing Dependencies
```bash
# Install PyInstaller for building executables
pip install pyinstaller
```

### Running the Tool
```bash
# During development, run directly with Python
python3 stash-away.py <command>

# After building, run the executable
./dist/stash-away <command>
```

### Available Commands
- `init <url> [--identity-file <path>]` - Initialize backup repository URL with optional SSH key
- `status` - Show current configuration and repository status
- `push` - Back up current changes to remote repository
- `archive` - Create local compressed archive
- `list` - List all backups in remote repository
- `diff <backup_name>` - Compare current state with backup
- `restore <backup_name>` - Restore backup to new branch

## Architecture

### Single-File Design
The entire application is contained in `stash-away.py` with clear functional sections:

1. **Utility Functions** (lines 9-39)
   - `run_command()` - Central subprocess execution with error handling
   - `is_git_repository()` - Git repository detection

2. **Git Backup Logic** (lines 40-157)
   - Uses Git config to store backup URL (`backup.url`)
   - Creates timestamped backup branches
   - Stashes uncommitted changes before backup
   - Pushes to remote without adding as remote

3. **Archive Logic** (lines 158-186)
   - Creates tar.gz archives respecting .gitignore
   - Falls back to archiving all files if not in Git repo

4. **CLI Interface** (lines 187-228)
   - Uses argparse with subcommands
   - Each command maps to a specific function

### Key Design Patterns

1. **Error Handling**: Centralized in `run_command()` with proper exit codes
2. **Git Integration**: Direct subprocess calls to git commands
3. **No External Dependencies**: Uses only Python standard library
4. **Stateless Operations**: Each command is independent
5. **SSH Key Management**: Stores identity file path in git config and uses GIT_SSH_COMMAND for authentication

### Important Implementation Details

- Backup branches follow pattern: `backup/YYYY-MM-DD_HH-MM-SS`
- Restore branches follow pattern: `restore/YYYY-MM-DD_HH-MM-SS`
- Git config stores backup URL under `backup.url` key
- Git config stores SSH identity file under `backup.identityFile` key
- Temporary branches are created and cleaned up during operations
- All Git operations assume the current directory is the repository root

## Development Notes

- No test suite exists - manual testing required
- No linting configuration - follow existing code style
- PyInstaller spec file is pre-configured for macOS
- The project itself is not a Git repository (located at `/Users/dimitri.missoh/dev/workspace/private/private-fork/`)