echo "******************"
echo "exporting from poetry to requirements.txt"
sudo apt install python3.8-venv
echo "installing poetry..."
curl -sSL https://install.python-poetry.org | python3 - --preview
#curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
echo "finished poetry installation..."

#echo
#echo "adding poetry to path"
#export PATH="$HOME/.local/bin:$PATH"

echo -e "\r\n"
echo "poetry version:"
$HOME/.local/bin/poetry --version

echo -e "\r\n"
echo "exporting..."
$HOME/.local/bin/poetry export -f requirements.txt -o requirements.txt --without-hashes

echo -e "\r\n"
printf "done!"
echo "******************"