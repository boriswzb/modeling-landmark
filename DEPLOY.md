# 在其他服务器上部署

这个仓库包含两部分：

1. **静态查看器**：`viewer/` + `Giza_Pyramids.glb`，只需要 HTTP 静态服务，不需要 Blender。
2. **可编辑源场景**：`Giza_Pyramids.blend` + 脚本 + `textures/`，需要 Blender 4.5 或 Python 3.11 + `bpy` 才能重新生成。

## 最快方式：只部署查看器

```bash
git clone https://github.com/boriswzb/modeling-landmark.git
cd modeling-landmark
python3 -m http.server 8080 --bind 0.0.0.0
```

打开：

```
http://<服务器IP>:8080/viewer/
```

如果使用 Nginx：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    root /var/www/modeling-landmark;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # GLB 较大，建议开启 gzip/brotli；不要缓存错误版本
    location ~* \.glb$ {
        add_header Cache-Control "public, max-age=3600";
        types { model/gltf-binary glb; }
    }
}
```

把仓库内容放到 `/var/www/modeling-landmark`，确保目录结构是：

```
modeling-landmark/
├── Giza_Pyramids.glb
├── viewer/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── vendor/
└── ...
```

`viewer/app.js` 通过 `../Giza_Pyramids.glb?v=3` 加载模型，因此 **`viewer/` 和 GLB 必须保持同级**。

## GitHub Pages

仓库根目录已经按静态站点组织，可以直接开启 GitHub Pages：

- Source: `Deploy from a branch`
- Branch: `main` / root

访问 `https://boriswzb.github.io/modeling-landmark/viewer/`。

> GitHub Pages 对单文件有 100 MB 限制；当前 GLB 约 26 MB、Blend 约 32 MB，均低于限制。若后续换更高精度扫描，建议把大文件放到对象存储或使用 Git LFS。

## 重新生成模型

需要 Blender 4.5 的 Python 模块：

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install bpy==4.5.14
python make_textures.py
python make_sky.py
python build_giza.py --export
```

`build_giza.py` 默认读取 `assets/sphinx_warehouse.glb`，请确保该文件随仓库一起下载。

## 注意

- 不能直接双击 `viewer/index.html` 用 `file://` 打开；浏览器会阻止 GLB / ES Module 加载。
- 若页面空白，先确认 `Giza_Pyramids.glb` 与 `viewer/` 同级，并检查服务器是否返回 200。
- Sphinx 模型为低多边形素材，来源与许可见 `assets/README.md`；公开发布/商用前请核对 3D Warehouse 条款。
