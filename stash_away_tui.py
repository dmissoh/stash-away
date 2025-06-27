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
try:
    import termios
    import tty
    TERMIOS_AVAILABLE = True
except ImportError:
    TERMIOS_AVAILABLE = False
from rich.text import Text
from rich.align import Align
from rich import box
import time

class StashAwayTUI:
    def __init__(self):
        self.console = Console()
        self.running = True
        self.selected_index = 0  # Currently selected menu item
        self.menu_items = [
            ("Show Status", self.show_status),
            ("Push Backup", self.push_backup),
            ("Create Archive", self.create_archive),
            ("List Backups", self.list_backups),
            ("Initialize Repository", self.initialize),
            ("Compare with Backup", self.compare_backup),
            ("Restore Backup", self.restore_backup),
            ("Quit", self.quit_app)
        ]
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
                timeout=120  # Increased timeout for network operations like restore
            )
            
            # Combine stdout and stderr for complete output
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            return output if output else "Command completed with no output."
        except subprocess.TimeoutExpired:
            return "[red]Error: Command timed out after 2 minutes. This may indicate network issues or authentication problems.[/red]"
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
    
    def get_key(self):
        """Get a single keypress from the user"""
        if not TERMIOS_AVAILABLE:
            # Fallback for systems without termios (like Windows)
            self.console.print("[dim]Enter your choice: [/dim]", end="")
            try:
                choice = input().strip().upper()
                if choice in ['1', '2', '3', '4', '5', '6', '7']:
                    return choice
                elif choice in ['Q', 'QUIT']:
                    return 'QUIT'
                else:
                    return 'ENTER'  # Default to enter
            except:
                return 'QUIT'
        
        try:
            # Save original terminal settings
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            
            try:
                # Set terminal to raw mode
                tty.setraw(sys.stdin.fileno())
                
                # Read a single character
                key = sys.stdin.read(1)
                
                # Handle escape sequences (arrow keys)
                if ord(key) == 27:  # ESC sequence
                    key += sys.stdin.read(2)
                    if key == '\x1b[A':  # Up arrow
                        return 'UP'
                    elif key == '\x1b[B':  # Down arrow
                        return 'DOWN'
                    elif key == '\x1b[C':  # Right arrow
                        return 'RIGHT'
                    elif key == '\x1b[D':  # Left arrow
                        return 'LEFT'
                    else:
                        return 'ESC'
                elif ord(key) == 10 or ord(key) == 13:  # Enter
                    return 'ENTER'
                elif ord(key) == 3:  # Ctrl+C
                    return 'CTRL_C'
                elif key == 'q' or key == 'Q':
                    return 'QUIT'
                elif key in '12345678':
                    return key
                else:
                    return key.upper()
                    
            finally:
                # Restore original terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
        except Exception:
            # Fallback to regular input if terminal manipulation fails
            try:
                return input().strip()
            except:
                return 'QUIT'
    
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
        """Display the main menu with cursor navigation"""
        table = Table(show_header=False, box=None)
        table.add_column("Selector", style="cyan", width=3)
        table.add_column("Key", style="cyan", width=5)
        table.add_column("Action", style="white")
        
        for idx, (action_name, _) in enumerate(self.menu_items):
            key = str(idx + 1) if idx < 7 else "q"
            
            if idx == self.selected_index:
                # Highlight selected item
                selector = "▶"
                key_style = "[bold reverse cyan]" + key + "[/bold reverse cyan]"
                action_style = "[bold reverse white]" + action_name + "[/bold reverse white]"
            else:
                selector = " "
                key_style = "[bold]" + key + "[/bold]"
                action_style = action_name
            
            table.add_row(selector, key_style, action_style)
        
        menu_panel = Panel(
            table,
            title="[bold]Main Menu[/bold] [dim](↑↓ to navigate, Enter to select, q to quit)[/dim]",
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
            cmd = f"python3 stash-away.py restore {shlex.quote(backup_name)} --yes"
            with self.console.status("[bold green]Restoring backup (this may take a while)...[/bold green]", spinner="dots12"):
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
    
    def quit_app(self):
        """Quit the application"""
        if Confirm.ask("[yellow]Are you sure you want to quit?[/yellow]"):
            self.console.print("\n[bold green]Goodbye![/bold green]")
            self.running = False
    
    def run(self):
        """Main application loop with cursor navigation"""
        while self.running:
            self.console.clear()
            self.show_header()
            self.show_menu()
            
            # Show navigation instructions
            self.console.print("[dim]Use ↑↓ arrows to navigate, Enter to select, or press number keys[/dim]")
            
            try:
                key = self.get_key()
                
                if key == 'UP':
                    self.selected_index = (self.selected_index - 1) % len(self.menu_items)
                elif key == 'DOWN':
                    self.selected_index = (self.selected_index + 1) % len(self.menu_items)
                elif key == 'ENTER':
                    # Execute selected menu item
                    _, action = self.menu_items[self.selected_index]
                    action()
                elif key == 'QUIT' or key == 'CTRL_C':
                    self.quit_app()
                elif key in '12345678':
                    # Direct number selection (legacy support)
                    try:
                        index = int(key) - 1
                        if 0 <= index < len(self.menu_items):
                            self.selected_index = index
                            _, action = self.menu_items[index]
                            action()
                    except (ValueError, IndexError):
                        self.console.print("[red]Invalid option. Please try again.[/red]")
                        time.sleep(1)
                elif key == 'Q':
                    self.quit_app()
                else:
                    # For any other key, just refresh the display
                    continue
                    
            except KeyboardInterrupt:
                self.quit_app()
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
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