echo "checking requirements.txt exists"
if [ -f requirements.txt ]; then
   echo "requirements.txt does exist, continuing..."
else
   echo "could not find requirements.txt!"
   exit 1
fi