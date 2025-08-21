#!/bin/bash

# Config
REPO_DIR="repos"
OUTPUT_FILE="repo_metadata.tsv"

# Guardar el directorio original
ROOT_DIR=$(pwd)

# Crear archivo temporal con encabezado
echo -e "repo_slug\tdefault_branch\tcommits_count\tfirst_commit_iso\tlast_commit_iso\tcontributors_count\tsize_on_disk_mb\tlines_of_code" > "$OUTPUT_FILE"

# Iterar sobre cada carpeta de repositorio
for REPO_PATH in "$REPO_DIR"/*; do
  if [ -d "$REPO_PATH/.git" ]; then
    REPO_NAME=$(basename "$REPO_PATH")
    echo "📦 Processing $REPO_NAME"

    pushd "$REPO_PATH" > /dev/null

    # Obtener rama por defecto
    default_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

    # Contar commits
    commits_count=$(git rev-list --count HEAD 2>/dev/null)

    # Fechas de primer y último commit
    commit_dates=($(git log --reverse --format=%aI 2>/dev/null))
    first_commit="${commit_dates[0]}"
    last_commit="${commit_dates[-1]}"

    # Contar contribuidores únicos
    contributors_count=$(git shortlog -sne 2>/dev/null | wc -l)

    # Tamaño en MB del repo
    size_on_disk_kb=$(du -sk . | cut -f1)
    size_on_disk_mb=$((size_on_disk_kb / 1024))

    # Contar líneas de código usando wc
    lines_of_code=0
    while IFS= read -r -d '' file; do
      ext="${file##*.}"
      case "$ext" in
        jpg|jpeg|png|gif|pdf|zip|exe|mp4|mov|avi|mp3|ogg|ttf|otf|svg)
          continue
          ;;
        *)
          file_lines=$(wc -l < "$file" 2>/dev/null)
          lines_of_code=$((lines_of_code + file_lines))
          ;;
      esac
    done < <(git ls-files -z)

    popd > /dev/null

    # Escribir datos al archivo de salida
    echo -e "$REPO_NAME\t$default_branch\t$commits_count\t$first_commit\t$last_commit\t$contributors_count\t$size_on_disk_mb\t$lines_of_code" >> "$OUTPUT_FILE"
    echo "✅ Saved metadata for $REPO_NAME"
  fi
done

echo "🎉 Metadata collection complete → $OUTPUT_FILE"
