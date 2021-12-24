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
printf "done!"
echo "******************"