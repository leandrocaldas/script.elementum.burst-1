#!/bin/bash

set -euo pipefail

POT_FILE="resources/language/messages.pot"

if [ ! -f "$POT_FILE" ]; then
  echo "⚠️ Arquivo $POT_FILE não encontrado!"
  exit 1
fi

echo "🚀 Iniciando merge de novas entradas do messages.pot para os arquivos strings.po..."

for po_file in resources/language/*/strings.po; do
  if [ -f "$po_file" ]; then
    echo "📄 Atualizando $po_file"

    TMP_FILE="$(mktemp)"

    # Mescla o .po atual com o .pot (preservando traduções existentes)
    msgcat --use-first --no-wrap "$po_file" "$POT_FILE" -o "$TMP_FILE"
    mv "$TMP_FILE" "$po_file"

    echo "🖥️ Formatando $po_file para msgid em linha única (sem alterar msgstr)..."

    # Junta msgid multilinha em uma linha só com awk
    awk '
      BEGIN { msgid = ""; inside = 0 }
      /^msgid ""$/ { inside = 1; msgid = ""; next }
      inside && /^"/ {
        gsub(/^"/, "", $0)
        gsub(/"$/, "", $0)
        msgid = msgid $0
        next
      }
      inside {
        print "msgid \"" msgid "\""
        print $0
        inside = 0
        next
      }
      { print }
    ' "$po_file" > "${po_file}.tmp" && mv "${po_file}.tmp" "$po_file"

    echo "✅ Atualizado: $po_file"
  else
    echo "⚠️ Arquivo não encontrado: $po_file"
  fi
done

echo "🎉 Merge completo. Pronto para verificação de alterações no Git pelo workflow."
