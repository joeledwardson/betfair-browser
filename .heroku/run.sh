echo "******************"
echo "exporting from poetry to requirements.txt"

echo "installing poetry..."
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
echo "finished poetry installation..."

echo -e " \r\n"
echo "poetry version:"
$HOME/.poetry/bin/poetry --version

echo -e " \r\n"
echo "exporting..."
$HOME/.poetry/bin/poetry export -f requirements.txt -o requirements.txt --without-hashes

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