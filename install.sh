#!/bin/sh
# Installs the bots into a repository checkout: ./install.sh /path/to/repo
# Always refreshes .bot/bot.py and .bot/test_bot.py; never overwrites your project.toml,
# CONVENTIONS.md or workflows.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
dst=${1:?usage: $0 /path/to/repo}
[ -d "$dst/.git" ] || { echo "$dst is not a git checkout" >&2; exit 1; }
mkdir -p "$dst/.bot" "$dst/.github/workflows"
cp "$here/bot/bot.py" "$here/bot/test_bot.py" "$dst/.bot/"
for f in .bot/project.toml .bot/CONVENTIONS.md .github/workflows/bot.yml .github/workflows/codeql.yml; do
    if [ -e "$dst/$f" ]; then echo "kept     $f"; else cp "$here/templates/$f" "$dst/$f"; echo "created  $f"; fi
done
echo "bot.py from $(git -C "$here" describe --always --dirty 2>/dev/null || echo '?')"
echo "Next: fill in the TODOs of .bot/project.toml and .bot/CONVENTIONS.md, check that your CI"
echo "workflows have 'workflow_dispatch:', then follow the README's GitHub setup."
