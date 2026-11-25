#!/bin/sh
# Maven on the modules a change touches (and what they need), never the whole 40-module build.
# Goes to .bot/mvn-changed.sh: protected, so the bots run it but can't edit it.
#
#   .bot/mvn-changed.sh check   compile + Checkstyle + license headers (-Pdev), no tests
#   .bot/mvn-changed.sh tests   the same, plus the test classes the change adds or edits
#   .bot/mvn-changed.sh list    print the modules and test classes, run nothing
#
# A change is the work tree against its merge base with origin/main, new files included.
set -eu
base=$(git merge-base origin/main HEAD)
files=$( { git diff --name-only "$base"; git ls-files --others --exclude-standard; } | sort -u)

modules=""
tests=""
for f in $files; do
    d=$(dirname "$f")
    # the nearest directory with a pom.xml; the root pom is protected, never a module here
    while [ "$d" != "." ] && [ ! -f "$d/pom.xml" ]; do d=$(dirname "$d"); done
    [ "$d" = "." ] && continue
    case ",$modules," in *",$d,"*) ;; *) modules="${modules:+$modules,}$d" ;; esac
    case "$f" in
        */src/test/java/*.java)
            c=$(basename "$f" .java)
            case ",$tests," in *",$c,"*) ;; *) tests="${tests:+$tests,}$c" ;; esac ;;
    esac
done

mode=${1:-check}
if [ "$mode" = list ]; then
    echo "modules: ${modules:-none}"
    echo "tests:   ${tests:-none}"
    exit 0
fi
if [ -z "$modules" ]; then
    echo "no Maven module changed: nothing to build"
    exit 0
fi

set -- -B -ntp -Pdev -pl "$modules" -am \
    -Dorg.apache.activemq.artemis.core.io.aio.AIOSequentialFileFactory.DISABLED=AnythingNotNull
if [ "$mode" = tests ] && [ -n "$tests" ]; then
    # only these classes, wherever they live; the modules -am pulls in run none of theirs
    exec mvn "$@" verify -Dtest="$tests" -Dsurefire.failIfNoSpecifiedTests=false \
        -DskipUnitTests=false -DskipIntegrationTests=false -DfailIfNoTests=false
fi
exec mvn "$@" verify -DskipTests
