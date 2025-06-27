#!/usr/bin/env python3
import argparse
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
import os

# --- UTILITY FUNCTIONS ---

def run_command(command, capture_output=False, check=True, env=None):
    """Executes a shell command and handles errors."""
    try:
        # If env is provided, merge it with current environment
        if env:
            import os
            command_env = os.environ.copy()
            command_env.update(env)
        else:
            command_env = None
            
        result = subprocess.run(
            command,
            text=True,
            capture_output=capture_output,
            check=check,
            encoding='utf-8',
            env=command_env
        )
        return result
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is it in your PATH?", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        if e.stdout:
            print(f"""STDOUT:
{e.stdout}""", file=sys.stderr)
        if e.stderr:
            print(f"""STDERR:
{e.stderr}""", file=sys.stderr)
        sys.exit(1)

def is_git_repository():
    """Checks if the current directory is a Git repository."""
    result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], capture_output=True, text=True)
    return result.stdout.strip() == 'true'

# --- GIT BACKUP LOGIC ---

def init_backup_repo(url, identity_file=None):
    """Sets the backup repository URL and optional SSH identity file in the local Git config."""
    if not is_git_repository():
        print("Error: Not a Git repository. Cannot initialize for backup.", file=sys.stderr)
        return
    run_command(['git', 'config', f'backup.url', url])
    print(f"Backup repository URL set to: {url}")
    
    if identity_file:
        run_command(['git', 'config', f'backup.identityFile', identity_file])
        print(f"SSH identity file set to: {identity_file}")

def get_backup_repo_url():
    """Retrieves the backup repository URL from the local Git config."""
    if not is_git_repository():
        return None
    result = run_command(['git', 'config', '--get', f'backup.url'], capture_output=True, check=False)
    return result.stdout.strip() or None

def get_backup_identity_file():
    """Retrieves the SSH identity file path from the local Git config."""
    if not is_git_repository():
        return None
    result = run_command(['git', 'config', '--get', f'backup.identityFile'], capture_output=True, check=False)
    return result.stdout.strip() or None

def get_git_env():
    """Returns environment variables for Git commands with SSH identity if configured."""
    identity_file = get_backup_identity_file()
    if identity_file:
        return {'GIT_SSH_COMMAND': f'ssh -i {identity_file} -o IdentitiesOnly=yes'}
    return None

def push_to_backup():
    """Pushes all local changes to a new branch in the backup repository."""
    if not is_git_repository():
        print("Error: Not a Git repository. Cannot proceed with backup.", file=sys.stderr)
        return

    backup_url = get_backup_repo_url()
    if not backup_url:
        print("Error: Backup repository URL not set. Please run 'init' first.", file=sys.stderr)
        return
    
    # Check for uncommitted changes
    status_result = run_command(['git', 'status', '--porcelain'], capture_output=True)
    if not status_result.stdout.strip():
        print("No changes to backup. Working directory is clean.")
        return

    print("Starting backup to personal Git repository...")

    current_branch = run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True).stdout.strip()
    print(f"Current branch: {current_branch}")

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_branch = f'backup/{timestamp}'
    print(f"Creating backup branch: {backup_branch}")

    run_command(['git', 'stash', 'push', '-u', '-m', f'Backup-stash for {backup_branch}'])
    print("Stashed uncommitted changes.")

    run_command(['git', 'checkout', '-b', backup_branch])

    run_command(['git', 'stash', 'pop'])
    print("Applied stashed changes to the backup branch.")

    run_command(['git', 'add', '.'])
    run_command(['git', 'commit', '-m', f'Backup snapshot: {timestamp}'])
    print("Committed all changes to the backup branch.")

    print(f"Pushing to backup repository at {backup_url}...")
    run_command(['git', 'push', backup_url, f'{backup_branch}:{backup_branch}'], env=get_git_env())
    print("Push successful.")

    print("Cleaning up...")
    run_command(['git', 'checkout', current_branch])
    run_command(['git', 'branch', '-D', backup_branch])
    print(f"Returned to branch '{current_branch}' and deleted local backup branch.")
    print("Backup complete!")
    print(f"Your changes are safely stored in branch '{backup_branch}' in your personal repository.")

def list_backups():
    """Lists all backup branches from the remote repository."""
    backup_url = get_backup_repo_url()
    if not backup_url:
        print("Error: Backup repository URL not set. Please run 'init' first.", file=sys.stderr)
        return

    print(f"Fetching backups from {backup_url}...")
    result = run_command(
        ['git', 'ls-remote', '--heads', backup_url, 'refs/heads/backup/*'],
        capture_output=True,
        env=get_git_env()
    )

    branches = result.stdout.strip().split('\n')
    if not any(branches):
        print("No backups found.")
        return

    print("Available backups:")
    for branch in branches:
        if branch:
            branch_name = branch.split('\t')[1].replace('refs/heads/', '')
            print(f"  - {branch_name}")

def diff_backup(backup_name):
    """Shows the diff between the current state and a specific backup."""
    backup_url = get_backup_repo_url()
    if not backup_url:
        print("Error: Backup repository URL not set. Please run 'init' first.", file=sys.stderr)
        return

    print(f"Fetching {backup_name} to compare...")
    run_command(['git', 'fetch', backup_url, f'{backup_name}:{backup_name}', '--no-tags'], env=get_git_env())

    print(f"\n--- Diff between current working directory and {backup_name} ---")
    subprocess.run(['git', 'diff', backup_name])
    print(f"--- End of diff ---")

    run_command(['git', 'branch', '-D', backup_name])

def restore_backup(backup_name, auto_confirm=False):
    """Restores a backup to a new local branch."""
    backup_url = get_backup_repo_url()
    if not backup_url:
        print("Error: Backup repository URL not set. Please run 'init' first.", file=sys.stderr)
        return

    restore_branch_name = f"restore/{backup_name.replace('backup/', '')}"
    
    # Check if restore branch already exists
    result = run_command(['git', 'branch', '--list', restore_branch_name], capture_output=True, check=False)
    if result.stdout.strip():
        print(f"Error: Branch '{restore_branch_name}' already exists.", file=sys.stderr)
        print(f"To restore anyway, first delete the existing branch:", file=sys.stderr)
        print(f"  git branch -D {restore_branch_name}", file=sys.stderr)
        return
    
    # Confirm before restoring (unless auto-confirmed)
    if not auto_confirm:
        response = input(f"This will create a new branch '{restore_branch_name}' with the backup contents. Continue? (y/N): ")
        if response.lower() != 'y':
            print("Restore cancelled.")
            return
    
    print(f"Fetching and restoring {backup_name} to a new local branch: {restore_branch_name}")

    try:
        # First check if the backup exists in the remote
        print("Checking if backup exists...")
        list_result = run_command(
            ['git', 'ls-remote', '--heads', backup_url, f'refs/heads/{backup_name}'],
            capture_output=True,
            env=get_git_env(),
            check=False
        )
        
        if not list_result.stdout.strip():
            print(f"Error: Backup '{backup_name}' not found in the remote repository.", file=sys.stderr)
            return
        
        # Fetch the backup branch
        print("Fetching backup from remote repository...")
        run_command(['git', 'fetch', backup_url, f'{backup_name}:{restore_branch_name}'], env=get_git_env())

        # Switch to the restore branch
        print(f"Switching to branch '{restore_branch_name}'...")
        run_command(['git', 'checkout', restore_branch_name])

        print(f"\nSuccessfully restored backup.")
        print(f"Your project is now on branch '{restore_branch_name}' with the contents of {backup_name}.")
        print("You can now review the changes, commit, or switch back to your main branch.")
        
    except Exception as e:
        print(f"Error during restore: {e}", file=sys.stderr)
        # Try to clean up if restore branch was created but checkout failed
        result = run_command(['git', 'branch', '--list', restore_branch_name], capture_output=True, check=False)
        if result.stdout.strip():
            print(f"Cleaning up partially created branch '{restore_branch_name}'...")
            run_command(['git', 'branch', '-D', restore_branch_name], check=False)

# --- FILESYSTEM ARCHIVE LOGIC ---

def create_archive():
    """Creates a compressed tarball of the project, respecting .gitignore."""
    if not is_git_repository():
        print("Warning: Not a Git repository. Archiving all files without respecting .gitignore.")
        files_to_archive = ['.']
    else:
        result = run_command(['git', 'ls-files', '-c', '-o', '--exclude-standard'], capture_output=True)
        files_to_archive = result.stdout.strip().split('\n')

    if not files_to_archive:
        print("No files to archive.", file=sys.stderr)
        return

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    archive_name = f'stash-away-backup-{timestamp}.tar.gz'
    print(f"Creating archive: {archive_name}")

    try:
        with tarfile.open(archive_name, "w:gz") as tar:
            for item in files_to_archive:
                if item:
                    print(f"  - Adding {item}")
                    tar.add(item, arcname=item)
        print(f"Successfully created archive: {archive_name}")
    except Exception as e:
        print(f"Error creating archive: {e}", file=sys.stderr)

# --- MAIN CLI ---

def show_status():
    """Shows current backup configuration and repository status."""
    if not is_git_repository():
        print("Error: Not a Git repository.", file=sys.stderr)
        return
        
    print("=== Stash-Away Status ===")
    
    # Show configuration
    backup_url = get_backup_repo_url()
    identity_file = get_backup_identity_file()
    print(f"\nConfiguration:")
    print(f"  Backup URL: {backup_url or 'Not configured (run: stash-away init <url>)'}")
    print(f"  SSH Identity: {identity_file or 'Using default SSH configuration'}")
    
    # Show repository info
    current_branch = run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True).stdout.strip()
    print(f"\nRepository:")
    print(f"  Current branch: {current_branch}")
    
    # Show uncommitted changes
    status_result = run_command(['git', 'status', '--porcelain'], capture_output=True)
    if status_result.stdout.strip():
        print(f"  Uncommitted changes: Yes")
    else:
        print(f"  Uncommitted changes: No")
    
    # Show last backup info if available
    if backup_url:
        print(f"\nFetching backup information...")
        result = run_command(
            ['git', 'ls-remote', '--heads', backup_url, 'refs/heads/backup/*'],
            capture_output=True,
            env=get_git_env(),
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            branches = result.stdout.strip().split('\n')
            last_backup = branches[-1].split('\t')[1].replace('refs/heads/', '') if branches else None
            print(f"  Last backup: {last_backup}")
            print(f"  Total backups: {len(branches)}")
        else:
            print(f"  No backups found or unable to connect to backup repository")

def show_help():
    """Display comprehensive help information."""
    help_text = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                               STASH-AWAY HELP                               ║
║                        Git Repository Backup Tool                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESCRIPTION:
    Stash-Away helps you backup Git repositories to personal backup repositories
    or create local archives. Perfect for developers who need personal backups
    of work projects or want to snapshot progress without affecting main repos.

QUICK START:
    For beginners, use the interactive interface:
        stash-away ui

COMMANDS:

┌─ SETUP ─────────────────────────────────────────────────────────────────────┐
│ init <url> [--identity-file <path>]                                        │
│     Initialize backup repository URL with optional SSH key                 │
│     Example: stash-away init git@github.com:user/backups.git              │
│              stash-away init --identity-file ~/.ssh/id_rsa_personal \\      │
│                         git@github.com:personal/backups.git               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ BACKUP ────────────────────────────────────────────────────────────────────┐
│ push                                                                        │
│     Create timestamped backup of current state to remote repository        │
│     Example: stash-away push                                               │
│                                                                             │
│ archive                                                                     │
│     Create local compressed archive respecting .gitignore                  │
│     Example: stash-away archive                                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ MANAGE ────────────────────────────────────────────────────────────────────┐
│ list                                                                        │
│     List all available backups in remote repository                        │
│     Example: stash-away list                                               │
│                                                                             │
│ status                                                                      │
│     Show current backup configuration and repository status                │
│     Example: stash-away status                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ COMPARE & RESTORE ─────────────────────────────────────────────────────────┐
│ diff <backup_name>                                                          │
│     Compare current state with a specific backup                           │
│     Example: stash-away diff backup/2025-06-27_15-30-00                   │
│                                                                             │
│ restore <backup_name> [--yes]                                              │
│     Restore backup to new local branch (use --yes to skip confirmation)   │
│     Example: stash-away restore backup/2025-06-27_15-30-00                │
│              stash-away restore backup/2025-06-27_15-30-00 --yes          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ INTERFACE ─────────────────────────────────────────────────────────────────┐
│ ui                                                                          │
│     Launch interactive text-based user interface                           │
│     Navigation: ↑↓ arrows, Enter to select, Q to quit                     │
│     Example: stash-away ui                                                 │
│                                                                             │
│ help                                                                        │
│     Show this help message                                                  │
│     Example: stash-away help                                               │
└─────────────────────────────────────────────────────────────────────────────┘

WORKFLOW EXAMPLES:

  First-time setup:
    stash-away init git@github.com:myuser/my-backups.git
    stash-away push
    
  Daily workflow:
    stash-away push              # Backup current work
    stash-away archive           # Create local snapshot
    
  Working with backups:
    stash-away list              # See available backups
    stash-away diff backup/2025-06-27_15-30-00    # Compare with backup
    stash-away restore backup/2025-06-27_15-30-00 # Restore if needed

CONFIGURATION:
    Settings are stored in your project's Git config:
    - backup.url: The backup repository URL
    - backup.identityFile: SSH key path (optional)
    
    View settings: git config --get backup.url

SSH KEYS:
    Use different SSH keys for work and personal repositories:
    stash-away init --identity-file ~/.ssh/id_rsa_personal \\
                   git@github.com:personal/backups.git

For more information, visit: https://github.com/dmissoh/stash-away
"""
    print(help_text)

def main():
    """Main function to parse arguments and call the appropriate handler."""
    parser = argparse.ArgumentParser(
        description="A CLI tool to back up a project to a personal Git repository or a local archive.",
        epilog="Example usage: stash-away push\nFor beginners: stash-away ui (interactive interface)"
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    init_parser = subparsers.add_parser('init', help='Initialize the backup Git repository URL for the project.')
    init_parser.add_argument('url', help='The HTTPS or SSH URL of your personal backup Git repository.')
    init_parser.add_argument('--identity-file', help='Path to the SSH private key file to use for authentication (e.g., ~/.ssh/id_rsa_personal)')

    push_parser = subparsers.add_parser('push', help='Backup current changes to the remote Git repository.')

    archive_parser = subparsers.add_parser('archive', help='Create a local compressed archive of the project.')

    list_parser = subparsers.add_parser('list', help='List all available backups in the remote repository.')

    diff_parser = subparsers.add_parser('diff', help='Compare the current project state with a specific backup.')
    diff_parser.add_argument('backup_name', help='The full name of the backup branch to compare (e.g., backup/2025-06-27_15-30-00).')

    restore_parser = subparsers.add_parser('restore', help='Restore a backup to a new local branch.')
    restore_parser.add_argument('backup_name', help='The full name of the backup branch to restore.')
    restore_parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm restore without prompting')
    
    status_parser = subparsers.add_parser('status', help='Show current backup configuration and repository status.')
    
    ui_parser = subparsers.add_parser('ui', help='Launch interactive text-based user interface.')
    
    help_parser = subparsers.add_parser('help', help='Show detailed help and usage examples.')

    args = parser.parse_args()

    if args.command == 'init':
        init_backup_repo(args.url, args.identity_file)
    elif args.command == 'push':
        push_to_backup()
    elif args.command == 'archive':
        create_archive()
    elif args.command == 'list':
        list_backups()
    elif args.command == 'diff':
        diff_backup(args.backup_name)
    elif args.command == 'restore':
        restore_backup(args.backup_name, auto_confirm=args.yes)
    elif args.command == 'status':
        show_status()
    elif args.command == 'help':
        show_help()
    elif args.command == 'ui':
        # Check if we're in a git repository first
        if not is_git_repository():
            print("Error: Not in a git repository", file=sys.stderr)
            sys.exit(1)
        # Import and run TUI
        try:
            # Try importing rich first to give better error message
            try:
                import rich
            except ImportError:
                print("Error: The 'rich' library is required for the UI mode.", file=sys.stderr)
                print("Please install it with: pip install rich", file=sys.stderr)
                sys.exit(1)
            
            # Import and run the TUI
            import stash_away_tui
            app = stash_away_tui.StashAwayTUI()
            app.run()
        except ImportError as e:
            print("Error: Could not import TUI module.", file=sys.stderr)
            print(f"Details: {str(e)}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error running UI: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()