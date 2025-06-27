#!/usr/bin/env python3
import subprocess
import sys
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.prompt import Prompt, Confirm
import readline
from rich.text import Text
from rich.align import Align
from rich import box
import time

class StashAwayTUI:
    def __init__(self):
        self.console = Console()
        self.running = True
        # Enable readline for better input handling
        try:
            readline.set_startup_hook(None)
        except:
            pass
        
    def run_command(self, command):
        """Run a command and return output"""
        try:
            import shlex
            
            # Parse the command into parts
            cmd_parts = shlex.split(command)
            
            # Determine the correct way to call stash-away
            if getattr(sys, 'frozen', False):
                # Running in a PyInstaller bundle
                if cmd_parts[0] == "python3" and cmd_parts[1] == "stash-away.py":
                    # Replace python3 stash-away.py with the executable
                    cmd_parts = [sys.executable] + cmd_parts[2:]
            else:
                # Running from source
                if cmd_parts[0] == "python3" and cmd_parts[1] == "stash-away.py":
                    # Keep as is
                    pass
                else:
                    # Shouldn't happen but handle it
                    cmd_parts = ["python3", "stash-away.py"] + cmd_parts
            
            # Debug output (uncomment for debugging)
            # self.console.print(f"[dim]Debug: Running command: {' '.join(cmd_parts)}[/dim]")
            
            result = subprocess.run(
                cmd_parts, 
                capture_output=True, 
                text=True,
                timeout=30  # Add timeout to prevent hanging
            )
            
            # Combine stdout and stderr for complete output
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            return output if output else "Command completed with no output."
        except subprocess.TimeoutExpired:
            return "[red]Error: Command timed out after 30 seconds[/red]"
        except Exception as e:
            return f"[red]Error: {str(e)}[/red]"
    
    def safe_input(self, prompt_text, default="", strip_markup=True):
        """Safe input function that handles terminal escape sequences properly"""
        try:
            if strip_markup:
                # Remove rich markup for cleaner input
                import re
                clean_prompt = re.sub(r'\[/?[^\]]*\]', '', prompt_text)
                self.console.print(f"[cyan]{clean_prompt}[/cyan]", end="")
            else:
                self.console.print(prompt_text, end="")
            
            sys.stdout.flush()  # Ensure prompt is displayed immediately
            
            # Read input line with readline support for backspace handling
            try:
                result = input().strip()
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled[/yellow]")
                return default
            
            return result if result else default
        except (EOFError, KeyboardInterrupt):
            return default
        except Exception:
            # Fallback to basic input if rich features fail
            try:
                import re
                clean_prompt = re.sub(r'\[/?[^\]]*\]', '', prompt_text)
                print(clean_prompt, end="")
                result = input().strip()
                return result if result else default
            except:
                return default
    
    def show_header(self):
        """Display the header"""
        header = Panel(
            Align.center(
                "[bold yellow]STASH-AWAY[/bold yellow]\n[dim]Git Repository Backup Tool[/dim]",
                vertical="middle"
            ),
            box=box.DOUBLE,
            style="cyan",
            height=5
        )
        self.console.print(header)
        self.console.print()
    
    def show_menu(self):
        """Display the main menu"""
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Action", style="white")
        
        table.add_row("[bold]1[/bold]", "Show Status")
        table.add_row("[bold]2[/bold]", "Push Backup")
        table.add_row("[bold]3[/bold]", "Create Archive")
        table.add_row("[bold]4[/bold]", "List Backups")
        table.add_row("[bold]5[/bold]", "Initialize Repository")
        table.add_row("[bold]6[/bold]", "Compare with Backup")
        table.add_row("[bold]7[/bold]", "Restore Backup")
        table.add_row("[bold]q[/bold]", "Quit")
        
        menu_panel = Panel(
            table,
            title="[bold]Main Menu[/bold]",
            title_align="left",
            border_style="green",
            box=box.ROUNDED
        )
        
        self.console.print(menu_panel)
        self.console.print()
    
    def show_status(self):
        """Show repository status"""
        self.console.clear()
        self.show_header()
        
        with self.console.status("[bold green]Fetching status...[/bold green]"):
            output = self.run_command("python3 stash-away.py status")
        
        status_panel = Panel(
            output,
            title="[bold]Repository Status[/bold]",
            title_align="left",
            border_style="blue",
            box=box.ROUNDED
        )
        
        self.console.print(status_panel)
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def push_backup(self):
        """Push backup to remote repository"""
        self.console.clear()
        self.show_header()
        
        if Confirm.ask("[yellow]Create a new backup?[/yellow]"):
            with self.console.status("[bold green]Creating backup...[/bold green]", spinner="dots"):
                output = self.run_command("python3 stash-away.py push")
            
            if "Push successful." in output or "Backup complete!" in output:
                self.console.print(Panel(
                    output,
                    title="[bold green]✓ Backup Successful[/bold green]",
                    border_style="green",
                    box=box.ROUNDED
                ))
            else:
                self.console.print(Panel(
                    output,
                    title="[bold red]✗ Backup Failed[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
        
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def create_archive(self):
        """Create local archive"""
        self.console.clear()
        self.show_header()
        
        if Confirm.ask("[yellow]Create a local archive?[/yellow]"):
            with self.console.status("[bold green]Creating archive...[/bold green]", spinner="dots"):
                output = self.run_command("python3 stash-away.py archive")
            
            if "Successfully created archive:" in output:
                self.console.print(Panel(
                    output,
                    title="[bold green]✓ Archive Created[/bold green]",
                    border_style="green",
                    box=box.ROUNDED
                ))
            else:
                self.console.print(Panel(
                    output,
                    title="[bold red]✗ Archive Failed[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
        
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def list_backups(self):
        """List all backups"""
        self.console.clear()
        self.show_header()
        
        with self.console.status("[bold green]Fetching backups...[/bold green]"):
            output = self.run_command("python3 stash-away.py list")
        
        backups_panel = Panel(
            output,
            title="[bold]Available Backups[/bold]",
            title_align="left",
            border_style="blue",
            box=box.ROUNDED
        )
        
        self.console.print(backups_panel)
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def initialize(self):
        """Initialize backup repository"""
        self.console.clear()
        self.show_header()
        
        self.console.print(Panel(
            "[bold]Initialize Backup Repository[/bold]\n\n"
            "Enter the URL of your backup repository (e.g., git@github.com:user/backups.git)",
            border_style="yellow",
            box=box.ROUNDED
        ))
        
        url = self.safe_input("\nRepository URL: ")
        
        if url:
            ssh_key = self.safe_input("SSH Key Path (optional, press Enter to skip): ", "")
            
            # Properly escape the URL and SSH key path
            import shlex
            cmd_parts = ["python3", "stash-away.py", "init", url]
            if ssh_key:
                cmd_parts.extend(["--identity-file", ssh_key])
            
            cmd = " ".join(shlex.quote(part) for part in cmd_parts)
            
            with self.console.status("[bold green]Initializing...[/bold green]"):
                output = self.run_command(cmd)
            
            if "Backup repository URL set to:" in output:
                self.console.print(Panel(
                    output,
                    title="[bold green]✓ Initialization Successful[/bold green]",
                    border_style="green",
                    box=box.ROUNDED
                ))
            else:
                self.console.print(Panel(
                    output,
                    title="[bold red]✗ Initialization Failed[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
        
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def compare_backup(self):
        """Compare with a backup"""
        self.console.clear()
        self.show_header()
        
        # First list backups
        with self.console.status("[bold green]Fetching backups...[/bold green]"):
            list_output = self.run_command("python3 stash-away.py list")
        
        self.console.print(Panel(
            list_output,
            title="[bold]Available Backups[/bold]",
            border_style="blue",
            box=box.ROUNDED
        ))
        
        backup_name = self.safe_input("\nEnter backup name to compare: ")
        
        if backup_name:
            import shlex
            cmd = f"python3 stash-away.py diff {shlex.quote(backup_name)}"
            with self.console.status("[bold green]Comparing...[/bold green]"):
                output = self.run_command(cmd)
            
            self.console.print(Panel(
                output,
                title=f"[bold]Diff with {backup_name}[/bold]",
                border_style="yellow",
                box=box.ROUNDED
            ))
        
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def restore_backup(self):
        """Restore a backup"""
        self.console.clear()
        self.show_header()
        
        # First list backups
        with self.console.status("[bold green]Fetching backups...[/bold green]"):
            list_output = self.run_command("python3 stash-away.py list")
        
        self.console.print(Panel(
            list_output,
            title="[bold]Available Backups[/bold]",
            border_style="blue",
            box=box.ROUNDED
        ))
        
        backup_name = self.safe_input("\nEnter backup name to restore: ")
        
        if backup_name and Confirm.ask(f"[yellow]Restore {backup_name}?[/yellow]"):
            import shlex
            cmd = f"python3 stash-away.py restore {shlex.quote(backup_name)}"
            with self.console.status("[bold green]Restoring...[/bold green]"):
                output = self.run_command(cmd)
            
            if "Successfully restored backup." in output:
                self.console.print(Panel(
                    output,
                    title="[bold green]✓ Restore Successful[/bold green]",
                    border_style="green",
                    box=box.ROUNDED
                ))
            else:
                self.console.print(Panel(
                    output,
                    title="[bold red]✗ Restore Failed[/bold red]",
                    border_style="red",
                    box=box.ROUNDED
                ))
        
        self.console.print("\n[dim]Press Enter to continue...[/dim]")
        input()
    
    def run(self):
        """Main application loop"""
        while self.running:
            self.console.clear()
            self.show_header()
            self.show_menu()
            
            choice = self.safe_input("Select an option (1): ", "1")
            
            if choice == "1":
                self.show_status()
            elif choice == "2":
                self.push_backup()
            elif choice == "3":
                self.create_archive()
            elif choice == "4":
                self.list_backups()
            elif choice == "5":
                self.initialize()
            elif choice == "6":
                self.compare_backup()
            elif choice == "7":
                self.restore_backup()
            elif choice.lower() == "q":
                if Confirm.ask("[yellow]Are you sure you want to quit?[/yellow]"):
                    self.console.print("\n[bold green]Goodbye![/bold green]")
                    self.running = False
            else:
                self.console.print("[red]Invalid option. Please try again.[/red]")
                time.sleep(1)

def main():
    # Check if we're in a git repository
    if not os.path.exists('.git'):
        console = Console()
        console.print("[bold red]Error:[/bold red] Not in a git repository")
        sys.exit(1)
    
    try:
        app = StashAwayTUI()
        app.run()
    except KeyboardInterrupt:
        console = Console()
        console.print("\n[bold yellow]Interrupted by user[/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console = Console()
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)

# Only run main if this file is executed directly, not when imported
# This prevents the TUI from launching when included in PyInstaller bundle
if __name__ == "__main__" and not getattr(sys, 'frozen', False):
    main()