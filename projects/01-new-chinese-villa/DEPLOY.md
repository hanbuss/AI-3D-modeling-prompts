# 部署到 GitHub（三条路径，任选一条）


---

## 路径 A · 有 PAT 的情况（最快，一次命令）

1. 打开 <https://github.com/settings/tokens> → Generate new token (classic) → 勾 **repo** → 生成后复制。
2. 在本目录执行（把 `<PAT>` 换成你的 token）：

```bash
cd repo-cloudcrest

# 建仓库并推送（GitHub 不会自动建库，用 API 建一个空的）
curl -X POST https://api.github.com/user/repos \
  -H "Authorization: Bearer <PAT>" \
  -H "Accept: application/vnd.github+json" \
  -d '{"name":"cloudcrest-villa","description":"三层新中式别墅 · 程序化工程 + 离线 Three.js 查看器","private":false}'

git remote add origin https://<PAT>@github.com/hanbuss/cloudcrest-villa.git
git push -u origin main
```

> 推完记得把 remote 里的 token 摘掉：
> `git remote set-url origin https://github.com/hanbuss/cloudcrest-villa.git`

---

## 路径 B · 你手动建库 + 本地凭据登录

1. 网页建空仓库：<https://github.com/new> → 名字 `cloudcrest-villa` → **不要**勾 README/LICENSE（要空库）。
2. 本目录执行：

```bash
cd repo-cloudcrest
git remote add origin https://github.com/hanbuss/cloudcrest-villa.git
git push -u origin main
# 弹窗要求登录时用浏览器授权（Git Credential Manager），或用 PAT 当密码
```

---

## 路径 C · 完全离线搬运（本机没网也行）

`cloudcrest-villa.bundle` 是一个自带完整历史的单文件，可通过 U 盘 / 网盘带到任意有网的机器：

```bash
# 在能上网的机器上
git clone cloudcrest-villa.bundle cloudcrest-villa
cd cloudcrest-villa
git remote set-url origin https://github.com/hanbuss/cloudcrest-villa.git   # 先在网页建空库
git push -u origin main
```

---

## 开启在线查看器（GitHub Pages）

推上去之后：

1. 仓库 → **Settings → Pages**
2. Source 选 **GitHub Actions**（工作流已放在 `.github/workflows/pages.yml`，push 到 `main` 会自动发布）
3. 等 1–2 分钟，访问：

```
https://hanbuss.github.io/cloudcrest-villa/
```

仓库根 `index.html` 是项目索引页，点进去进各自查看器。

> ⚠️ 首次打开要下载 `villa/villa.glb`（约 57 MB），慢一点是正常的。
> 如果嫌大：`build_villa.py` 导出时加 `export_draco_mesh_compression_enable=True`，
> 再给 `viewer/index.html` 补 DRACOLoader（`vendor/DRACOLoader.js` + `vendor/draco/`），可压到 10 MB 级。

---

## 推送前自检

```bash
git -C repo-cloudcrest log --oneline          # 应有 1 个 commit
git -C repo-cloudcrest ls-files | wc -l       # 67
du -sh repo-cloudcrest                        # ~82 MB（含 57 MB 的 villa.glb）

# 本地起服务确认页面能开（不依赖 GitHub）
cd repo-cloudcrest && python -m http.server 8902
# → http://127.0.0.1:8902/projects/01-new-chinese-villa/viewer/index.html
```

> 文件体积：`villa.glb` 57 MB，低于 GitHub 单文件 100 MB 硬限制，可直接入库。
> 若以后超过 100 MB，改用 Git LFS：`git lfs track "*.glb"`。
