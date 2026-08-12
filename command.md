# InBody AI Scanner 常用指令小抄 (Cheat Sheet)

## 🚀 1. 啟動開發伺服器 (日常開發)

啟動 FastAPI 後端伺服器 (熱更新模式)：
uvicorn main:app --reload

啟動 Vue 3 前端開發伺服器：
npm run dev

--------------------------------------------------
## 📦 2. 後端套件管理 (Python / pip)

匯出當前環境的套件清單 (備份或上雲端時使用)：
pip freeze > requirements.txt

根據清單一次安裝所有所需套件 (換電腦或剛拉下專案時使用)：
pip install -r requirements.txt

--------------------------------------------------
## 🌐 3. 前端套件與打包管理 (Node.js / npm)

安裝新的前端套件：
npm install <套件名稱>

打包正式版網頁 (Production Build，準備正式上線時使用)：
npm run build

預覽打包後的正式版網頁 (檢查 build 出來的網頁是否正常)：
npm run preview

--------------------------------------------------
## 🌿 4. Git 版本控制日常 (存檔與備份)
git checkout -b branch
檢查目前有哪些檔案被修改過：
git status

將所有修改過的檔案加入暫存區：
git add .

正式提交一個版本紀錄 (請將引號內文字換成這次修改的重點)：
git commit -m "feat: 新增了歷史折線圖功能"

將最新的版本推送到 GitHub 雲端備份：
git push
git push -u origin branch

1.切換回本地的主線
git checkout main

2.把雲端剛剛合併好的最新進度拉下來
git pull origin main

3.刪除本地端已經完成任務的舊分支 (保持環境乾淨)
git branch -d branch

## ngrok
ngrok http 8000    
uvicorn main:app --host 0.0.0.0 --port 8000