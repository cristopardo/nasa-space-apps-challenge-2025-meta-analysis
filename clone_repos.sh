#!/bin/bash

# Config
CSV_FILE="data/spaceapps_winners_2021_2024.csv"
REPO_COLUMN="Github"
DEST_DIR="repos"

# Ensure destination exists
mkdir -p "$DEST_DIR"

# Get column index
HEADER=$(head -n 1 "$CSV_FILE")
IFS=',' read -ra COLUMNS <<< "$HEADER"

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

echo "🔍 Found column '$REPO_COLUMN' at index $col_index"
echo "📁 Cloning repos to '$DEST_DIR'..."

# Function to extract URL from CSV line respecting quotes
extract_url() {
  line="$1"
  echo "$line" | awk -v col=$((col_index+1)) '
    BEGIN {
      FPAT = "([^,]*)|(\"[^\"]+\")"
    }
    {
      gsub(/^"|"$/, "", $col)  # remove surrounding quotes
      print $col
    }'
}

# Read CSV line by line
tail -n +2 "$CSV_FILE" | while IFS= read -r line; do
  URL=$(extract_url "$line" | xargs)

  if [[ -z "$URL" ]]; then
    continue
  fi

  SLUG=$(echo "$URL" | sed -E 's~https?://(www\.)?github\.com/~~' | sed 's/\.git$//' | cut -d'/' -f1,2)
  SLUG_SAFE=$(echo "$SLUG" | tr '/' '__')

  if [[ -d "$DEST_DIR/$SLUG_SAFE" ]]; then
    echo "✅ Skipping $SLUG (already exists)"
    continue
  fi

  echo "⬇️ Cloning $SLUG → $DEST_DIR/$SLUG_SAFE"
  git clone "$URL" "$DEST_DIR/$SLUG_SAFE" --no-tags
done
