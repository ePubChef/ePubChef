# clone epubchef repo, push to empty repo (must be created first)
# inputs: 1. new repo name
# new repo will be owned by johnecobo and later shared to author/publisher
# requires johnecobo authentication

git clone https://github.com/ePubChef/ePubChef.git
mv ePubChef ePubChef_$1

cd ePubChef_$1
# ensure no accidental push to the real epubchef repo
git remote set-url --push origin no_push
# set repo name as remote name
git remote add $1 https://github.com/johnecobo/$1.git

# run reheat.sh instead of these
#cd ePubChef_pjones
#python3 cook.py pjonesbus

#git add .
#git commit -m "cooked in the cloud"
#git push pjones master

