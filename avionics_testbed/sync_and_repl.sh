#!/bin/bash

# Function to check if mpremote is installed
check_mpremote() {
    if ! command -v mpremote &> /dev/null; then
        echo "mpremote is not installed. Installing..."
        pip3 install mpremote
    fi
}

# Function to get last sync time
get_last_sync_time() {
    if [ -f ".last_sync_time" ]; then
        cat ".last_sync_time"
    else
        echo "0"  # Return 0 if file doesn't exist (epoch time)
    fi
}

# Function to update sync timestamp
update_sync_time() {
    date +%s > ".last_sync_time"
}

# Function to ensure directory exists on device
ensure_directory() {
    local dir_path="$1"
    local current=""
    
    # Split the path and create each directory level
    IFS='/' read -ra DIRS <<< "$dir_path"
    for dir in "${DIRS[@]}"; do
        if [ -n "$dir" ]; then
            if [ -z "$current" ]; then
                current="$dir"
            else
                current="$current/$dir"
            fi
            # Try to create directory, ignore errors
            mpremote fs mkdir ":$current" > /dev/null 2>&1
        fi
    done
}

# Function to sync files
sync_files() {
    echo "Checking for modified Python files..."
    last_sync=$(get_last_sync_time)
    any_files_synced=0

    # Use find to get all Python files, including those in subdirectories
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            file_mod_time=$(stat -f %m "$file")
            if [ $file_mod_time -gt $last_sync ]; then
                echo "Syncing modified file: $file"
                # Remove leading ./ from file path if present
                clean_path=${file#./}
                # Create directory on device if needed
                if [[ "$clean_path" == */* ]]; then
                    dir_path=$(dirname "$clean_path")
                    ensure_directory "$dir_path"
                fi
                mpremote cp "$clean_path" ":$clean_path"
                any_files_synced=1
            fi
        fi
    done < <(find . -name "*.py" ! -path "./.venv/*" ! -path "./env/*")

    if [ $any_files_synced -eq 0 ]; then
        echo "All files are up to date"
    fi

    update_sync_time
}

# Check and install mpremote if needed
check_mpremote

# Parse command line arguments
if [ "$1" == "--sync-only" ]; then
    sync_files
else
    sync_files
    if [ -f "main.py" ]; then
        echo "Running main.py..."
        mpremote run main.py
    else
        echo "No main.py found in current directory"
        exit 1
    fi
fi