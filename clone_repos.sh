#!/bin/bash

# Config
CSV_FILE="data/spaceapps_winners_2021_2024.csv"
REPO_COLUMN="Github"
DEST_DIR="repos"

# Ensure destination exists
mkdir -p "$DEST_DIR"

# Get header and index of repo column
HEADER=$(head -n 1 "$CSV_FILE")
IFS=',' read -ra COLUMNS <<< "$HEADER"

# Find index of desired column
col_index=-1
for i in "${!COLUMNS[@]}"; do
  if [[ "${COLUMNS[$i]}" == "$REPO_COLUMN" ]]; then
    col_index=$i
    break
  fi
done

if [[ $col_index -lt 0 ]]; then
  echo "❌ Column '$REPO_COLUMN' not found in CSV."
  exit 1
fi

# Read and process lines (excluding header)
tail -n +2 "$CSV_FILE" | while IFS=',' read -ra FIELDS; do
  URL="${FIELDS[$col_index]}"
  # Clean whitespace and quotes
  URL=$(echo "$URL" | tr -d '"' | xargs)
  if [[ -z "$URL" ]]; then
    continue
  fi

  # Get slug
  SLUG=$(echo "$URL" | sed -E 's~https?://(www\.)?github\.com/~~' | sed 's/\.git$//' | cut -d'/' -f1,2)
  SLUG_SAFE=$(echo "$SLUG" | tr '/' '__')

  # Check if already cloned
  if [[ -d "$DEST_DIR/$SLUG_SAFE" ]]; then
    echo "✅ Skipping $SLUG (already exists)"
    continue
  fi

  echo "⬇️ Cloning $SLUG → $DEST_DIR/$SLUG_SAFE"
  git clone "$URL" "$DEST_DIR/$SLUG_SAFE" --no-tags
done
