echo "******************"
echo "exporting from poetry to requirements.txt"

echo "installing poetry..."
curl -sSL https://install.python-poetry.org | python3 - --preview
echo "finished poetry installation..."

echo -e " \r\n"
echo "poetry version:"
$HOME/.local/bin/poetry --version

echo -e " \r\n"
echo "exporting..."
$HOME/.local/bin/poetry export -f requirements.txt -o requirements.txt --without-hashes

echo -e " \r\n"
echo "checking requirements.txt exists"
if [ -f requirements.txt ]; then
   echo "requirements.txt does exist, continuing..."
else
   echo "could not find requirements.txt!"
   exit 1
fi

echo -e " \r\n"
echo "done!"
echo "******************"