# for current project
git add . && \
git commit -m "$(date +'%Y-%m-%d')" && \



cp -r ~/projects/notes/bin_/* ~/projects/note_taking_github/ && \
cd ~/projects/note_taking_github/ && \
git add . && \
git commit -m "$(date +'%Y-%m-%d')" && \
git push


cp -r ~/projects/notes/nvim-lua/* ~/projects/note_taking_github/nvim-lua && \
cd ~/projects/note_taking_github/ && \
git add . && \
git commit -m "$(date +'%Y-%m-%d')" && \
git push

