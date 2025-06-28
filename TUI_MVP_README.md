# BorgBoi TUI MVP

This is a Minimum Viable Product (MVP) implementation of a Terminal User Interface (TUI) for borgboi using the Textual framework.

## Features Implemented

### 1. Repository List View

- Displays all borgboi repositories in a table format
- Shows repository name, host machine, size (GB), location, and last archive date
- Supports keyboard navigation (arrow keys) to select repositories
- Click or press Enter to view repository details
- **NEW**: Sortable columns with keyboard shortcuts:
  - Press `s` to sort by repository size (ascending/descending)
  - Press `d` to sort by last archive date (ascending/descending)  
  - Press `n` to sort by repository name (ascending/descending)
- Visual sort indicators (↑/↓) show current sort order in column headers

### 2. Repository Detail View

- Shows detailed information about the selected repository:
  - Repository name
  - Storage location 
  - Encryption mode
  - Last backup date
- Lists all archives in the repository
- Provides action buttons:
  - **Daily Backup**: Runs the daily backup routine (create, prune, compact, sync to S3)
  - **Refresh**: Reloads the archive list
  - **Back**: Returns to the repository list

### 3. Key Bindings

- `q`: Quit the application
- `r`: Refresh the current screen
- `s`: Sort repositories by size (toggles ascending/descending)
- `d`: Sort repositories by last archive date (toggles ascending/descending)
- `n`: Sort repositories by name (toggles ascending/descending)
- Arrow keys: Navigate tables
- Enter: Select items

### 4. Asynchronous Operations

- Repository and archive loading happens in background workers
- Daily backups run asynchronously with progress notifications
- UI remains responsive during long operations

## How to Use

### Launch the TUI

From the command line:
```bash
borgboi tui
```

Or using the provided demo script:
```bash
python demo_tui.py
```

### Navigation

1. **Main Screen**: Shows all repositories
   - Use arrow keys to highlight a repository
   - Press Enter or click to view details
   - **NEW**: Use `s`, `d`, or `n` keys to sort the table by different criteria
   - Help text shows available sorting options

2. **Detail Screen**: Shows repository details and archives
   - View repository metadata
   - See all archives
   - Run daily backup with a single click
   - Navigate back to the main list

### Sorting Functionality

The repository list can be sorted by three different criteria:

1. **Size Sorting (`s` key)**:
   - Sorts repositories by their deduplicated size in GB
   - Repositories without size information appear first (0.0 GB)
   - Toggles between ascending and descending order

2. **Date Sorting (`d` key)**:
   - Sorts repositories by their last backup/archive date
   - Repositories that have never been backed up appear first
   - Toggles between ascending and descending order

3. **Name Sorting (`n` key)**:
   - Sorts repositories alphabetically by name (case-insensitive)
   - Default sort order when the TUI starts
   - Toggles between ascending and descending order

Column headers show visual indicators (↑ for ascending, ↓ for descending) to indicate the current sort order.

## Technical Implementation

### File Structure

- `src/borgboi/tui.py`: Main TUI implementation
- Updated `src/borgboi/cli.py`: Added `tui` command

### Key Components

1. **BorgBoiApp**: Main application class
   - Manages screens and global keybindings
   - Handles CSS styling

2. **MainScreen**: Repository list screen
   - Loads repositories from DynamoDB
   - Displays in a DataTable widget
   - Shows sorting help text

3. **DetailScreen**: Repository detail view
   - Shows repository metadata
   - Lists archives
   - Provides action buttons

4. **RepoListWidget**: Custom widget for repository table
   - Handles row selection
   - Sends messages when repository selected
   - **NEW**: Implements sorting functionality with `SortOrder` enum
   - **NEW**: Provides keyboard bindings for sorting (`s`, `d`, `n`)
   - **NEW**: Updates table headers with sort indicators
   - **NEW**: Maintains sort state and provides visual feedback

5. **RepoDetailWidget**: Custom widget for repository details
   - Manages repository and archive data
   - Handles button actions
   - Uses Textual workers for async operations

6. **SortOrder**: Enumeration for different sort orders
   - Supports ascending/descending for name, size, and date
   - Used to track current sort state

### Integration Points

The TUI integrates with existing borgboi components:

- Uses `dynamodb.get_all_repos()` to fetch repositories
- Uses `borg.list_archives()` to get archive lists
- Calls `orchestrator.perform_daily_backup()` for backups
- Respects the same environment variables and configurations

## Future Enhancements

This MVP demonstrates the feasibility of a TUI for borgboi. Potential future additions:

1. **Create Repository**: Form to create new repositories
2. **Archive Operations**: Extract, delete archives
3. **Exclusion List Management**: View/edit exclusion patterns
4. **Live Progress**: Real-time progress bars for operations
5. **Search/Filter**: Search repositories and archives
6. **Offline Mode**: Support for offline operations
7. **Repository Restoration**: Restore from S3 backup
8. **Key Management**: Export/import repository keys
9. **Advanced Sorting**: Multi-column sorting, custom sort orders
10. **Column Customization**: Show/hide columns, resize columns

## Dependencies

The TUI requires Textual, which is already included in the project dependencies:

```toml
"textual[syntax]>=3.5.0",
```

## Notes

- The TUI currently requires AWS connectivity (no offline mode yet)
- Long operations (like daily backup) show notifications but not detailed progress
- Error handling displays user-friendly notifications
- Sorting is performed on the client side for responsive interaction
- Sort state is maintained per widget instance but not persisted between sessions

## MVP Feasibility Demonstration

This MVP successfully demonstrates:

1. **Integration Feasibility**: The TUI can seamlessly integrate with existing borgboi functionality without requiring major refactoring
2. **Performance**: Asynchronous operations keep the UI responsive even during long-running tasks
3. **User Experience**: The interface provides an intuitive way to manage repositories compared to memorizing CLI commands
4. **Architecture**: The separation of concerns between UI components and business logic works well
5. **Textual Framework**: Textual provides all necessary widgets and patterns for building a full-featured TUI
6. **Extensibility**: New features like sorting can be easily added without disrupting existing functionality

The MVP proves that a complete TUI for borgboi is not only feasible but would significantly enhance the user experience for managing Borg repositories.
