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

def restore_backup(backup_name):
    """Restores a backup to a new local branch."""
    backup_url = get_backup_repo_url()
    if not backup_url:
        print("Error: Backup repository URL not set. Please run 'init' first.", file=sys.stderr)
        return

    restore_branch_name = f"restore/{backup_name.replace('backup/', '')}"
    
    # Confirm before restoring
    response = input(f"This will create a new branch '{restore_branch_name}' with the backup contents. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Restore cancelled.")
        return
    
    print(f"Fetching and restoring {backup_name} to a new local branch: {restore_branch_name}")

    run_command(['git', 'fetch', backup_url, f'{backup_name}:{restore_branch_name}'], env=get_git_env())

    run_command(['git', 'checkout', restore_branch_name])

    print(f"\nSuccessfully restored backup.")
    print(f"Your project is now on branch '{restore_branch_name}' with the contents of {backup_name}.")
    print("You can now review the changes, commit, or switch back to your main branch.")

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

def main():
    """Main function to parse arguments and call the appropriate handler."""
    parser = argparse.ArgumentParser(
        description="A CLI tool to back up a project to a personal Git repository or a local archive.",
        epilog="Example usage: stash-away push"
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
    
    status_parser = subparsers.add_parser('status', help='Show current backup configuration and repository status.')
    
    ui_parser = subparsers.add_parser('ui', help='Launch interactive text-based user interface.')

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
        restore_backup(args.backup_name)
    elif args.command == 'status':
        show_status()
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