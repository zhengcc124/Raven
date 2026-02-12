#!/usr/bin/env python3
"""
Munin Journal - 静态站点生成器
基于 Python 的纯 HTML+CSS+JS 方案
"""

import os
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Post:
    """文章数据类"""
    title: str
    date: datetime
    content: str
    slug: str
    tags: List[str]
    excerpt: str
    raw_content: str


class Config:
    """配置管理"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
    
    def get(self, key: str, default=None):
        """获取配置项，支持点号分隔的路径"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    @property
    def all(self):
        return self._config


class MarkdownParser:
    """Markdown 解析器 - 简单实现"""
    
    # Frontmatter 正则
    FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    
    # 代码块
    CODE_BLOCK_RE = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)
    
    # 行内代码
    INLINE_CODE_RE = re.compile(r'`([^`]+)`')
    
    # 图片
    IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    
    # 链接
    LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    # 标题
    HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    # 粗体
    BOLD_RE = re.compile(r'\*\*([^\*]+)\*\*|__([^_]+)__')
    
    # 斜体
    ITALIC_RE = re.compile(r'\*([^\*]+)\*|_([^_]+)_')
    
    # 列表
    UL_RE = re.compile(r'^\s*[-\*]\s+(.+)$', re.MULTILINE)
    OL_RE = re.compile(r'^\s*(\d+)\.\s+(.+)$', re.MULTILINE)
    
    # 引用
    BLOCKQUOTE_RE = re.compile(r'^>\s*(.+)$', re.MULTILINE)
    
    # 分隔线
    HR_RE = re.compile(r'^\s*[-*_]{3,}\s*$', re.MULTILINE)
    
    # 段落
    PARAGRAPH_RE = re.compile(r'\n{2,}')
    
    @classmethod
    def parse(cls, content: str) -> Tuple[Dict, str]:
        """解析 Markdown 文件，返回 frontmatter 和正文"""
        frontmatter = {}
        body = content
        
        # 提取 frontmatter
        match = cls.FRONTMATTER_RE.match(content)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                pass
            body = content[match.end():]
        
        return frontmatter, body
    
    @classmethod
    def to_html(cls, content: str) -> str:
        """将 Markdown 转换为 HTML"""
        html = content
        
        # 转义 HTML 特殊字符
        html = html.replace('&', '&amp;')
        html = html.replace('<', '&lt;')
        html = html.replace('>', '&gt;')
        
        # 保存代码块（避免被其他规则处理）
        code_blocks = []
        def save_code_block(match):
            lang = match.group(1) or ''
            code = match.group(2)
            code_blocks.append((lang, code))
            return f'<!--CODE_BLOCK_{len(code_blocks)-1}-->'
        html = cls.CODE_BLOCK_RE.sub(save_code_block, html)
        
        # 处理代码块
        for i, (lang, code) in enumerate(code_blocks):
            code_html = f'<pre><code class="language-{lang}">{code.rstrip()}</code></pre>'
            html = html.replace(f'<!--CODE_BLOCK_{i}-->', code_html)
        
        # 行内代码
        def inline_code_replacer(match):
            code = match.group(1)
            return f'<code>{code}</code>'
        html = cls.INLINE_CODE_RE.sub(inline_code_replacer, html)
        
        # 图片（支持相对路径转换）
        def image_replacer(match):
            alt = match.group(1)
            src = match.group(2)
            # 转换相对路径
            if not src.startswith(('http://', 'https://', '/')):
                src = '../images/' + src
            return f'<img src="{src}" alt="{alt}" loading="lazy">'
        html = cls.IMAGE_RE.sub(image_replacer, html)
        
        # 链接
        def link_replacer(match):
            text = match.group(1)
            href = match.group(2)
            return f'<a href="{href}" target="_blank" rel="noopener">{text}</a>'
        html = cls.LINK_RE.sub(link_replacer, html)
        
        # 标题
        def heading_replacer(match):
            level = len(match.group(1))
            text = match.group(2)
            slug = re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '-').lower()
            return f'<h{level} id="{slug}">{text}</h{level}>'
        html = cls.HEADING_RE.sub(heading_replacer, html)
        
        # 粗体
        html = cls.BOLD_RE.sub(r'<strong>\1\2</strong>', html)
        
        # 斜体
        html = cls.ITALIC_RE.sub(r'<em>\1\2</em>', html)
        
        # 分隔线
        html = cls.HR_RE.sub('<hr>', html)
        
        # 引用块
        def blockquote_replacer(match):
            content = match.group(1)
            return f'<blockquote>\n<p>{content}</p>\n</blockquote>'
        html = cls.BLOCKQUOTE_RE.sub(blockquote_replacer, html)
        
        # 无序列表
        def ul_replacer(match):
            items = cls.UL_RE.findall(html)
            if not items:
                return match.group(0)
            li_html = '\n'.join([f'<li>{item}</li>' for item in items])
            return f'<ul>\n{li_html}\n</ul>'
        
        # 处理列表（简化版）
        lines = html.split('\n')
        result = []
        in_ul = False
        in_ol = False
        
        for line in lines:
            ul_match = re.match(r'^(\s*)[-\*]\s+(.+)$', line)
            ol_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
            
            if ul_match:
                if not in_ul:
                    if in_ol:
                        result.append('</ol>')
                        in_ol = False
                    result.append('<ul>')
                    in_ul = True
                result.append(f'<li>{ul_match.group(2)}</li>')
            elif ol_match:
                if not in_ol:
                    if in_ul:
                        result.append('</ul>')
                        in_ul = False
                    result.append('<ol>')
                    in_ol = True
                result.append(f'<li>{ol_match.group(2)}</li>')
            else:
                if in_ul:
                    result.append('</ul>')
                    in_ul = False
                if in_ol:
                    result.append('</ol>')
                    in_ol = False
                result.append(line)
        
        if in_ul:
            result.append('</ul>')
        if in_ol:
            result.append('</ol>')
        
        html = '\n'.join(result)
        
        # 段落处理
        paragraphs = html.split('\n\n')
        processed = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            # 如果已经是块级元素，不包裹
            if p.startswith(('<h', '<ul', '<ol', '<blockquote', '<pre', '<hr', '<img')):
                processed.append(p)
            else:
                # 处理换行
                p = p.replace('\n', '<br>')
                processed.append(f'<p>{p}</p>')
        
        html = '\n\n'.join(processed)
        
        return html


class SiteBuilder:
    """站点构建器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.posts: List[Post] = []
        self.base_dir = Path(__file__).parent
        # content 在仓库根目录，不是 frontend/content
        self.content_dir = self.base_dir.parent.parent / 'content'
        self.output_dir = self.base_dir.parent / 'dist'
        self.templates_dir = self.base_dir / 'templates'
    
    def load_posts(self) -> List[Post]:
        """加载所有文章"""
        posts_dir = self.content_dir / 'posts'
        if not posts_dir.exists():
            print(f"警告: 文章目录不存在 {posts_dir}")
            return []
        
        posts = []
        # 使用 rglob 递归搜索所有子目录中的 .md 文件
        for md_file in sorted(posts_dir.rglob('*.md'), reverse=True):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                frontmatter, body = MarkdownParser.parse(content)
                
                # 提取日期
                date_str = frontmatter.get('date', '')
                if date_str:
                    try:
                        date = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
                    except ValueError:
                        date = datetime.fromtimestamp(md_file.stat().st_mtime)
                else:
                    date = datetime.fromtimestamp(md_file.stat().st_mtime)
                
                # 生成 slug
                slug = frontmatter.get('slug', '')
                if not slug:
                    slug = md_file.stem
                
                # 提取摘要（前 150 字符）
                excerpt = re.sub(r'[#\*\`\[\]\(\)!]', '', body).replace('\n', ' ')[:150].strip()
                if len(body) > 150:
                    excerpt += '...'
                
                post = Post(
                    title=frontmatter.get('title', md_file.stem),
                    date=date,
                    content=MarkdownParser.to_html(body),
                    slug=slug,
                    tags=frontmatter.get('tags', []) or [],
                    excerpt=excerpt,
                    raw_content=body
                )
                posts.append(post)
                
            except Exception as e:
                print(f"错误: 无法解析 {md_file}: {e}")
        
        # 按日期降序排序
        posts.sort(key=lambda p: p.date, reverse=True)
        return posts
    
    def load_template(self, name: str) -> str:
        """加载模板文件"""
        template_path = self.templates_dir / name
        if not template_path.exists():
            raise FileNotFoundError(f"模板不存在: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def render_template(self, template: str, **kwargs) -> str:
        """渲染模板"""
        # 简单的变量替换
        result = template
        
        # 替换 config 变量
        for key, value in self.config.all.items():
            if isinstance(value, str):
                result = result.replace(f'{{{{ config.{key} }}}}', value)
            elif isinstance(value, bool):
                result = result.replace(f'{{{{ config.{key} }}}}', 'true' if value else 'false')
        
        # 嵌套配置处理
        result = self._replace_nested_config(result, self.config.all, 'config')
        
        # 替换其他变量
        for key, value in kwargs.items():
            if isinstance(value, str):
                result = result.replace(f'{{{{ {key} }}}}', value)
            elif isinstance(value, bool):
                result = result.replace(f'{{{{ {key} }}}}', 'true' if value else 'false')
        
        return result
    
    def _replace_nested_config(self, template: str, config: dict, prefix: str) -> str:
        """递归替换嵌套配置"""
        result = template
        for key, value in config.items():
            full_key = f'{prefix}.{key}'
            if isinstance(value, dict):
                result = self._replace_nested_config(result, value, full_key)
            elif isinstance(value, str):
                result = result.replace(f'{{{{ {full_key} }}}}', value)
            elif isinstance(value, bool):
                result = result.replace(f'{{{{ {full_key} }}}}', 'true' if value else 'false')
        return result
    
    def format_date(self, date: datetime, fmt: str = None) -> str:
        """格式化日期"""
        if fmt is None:
            fmt = self.config.get('date_format', '%Y-%m-%d')
        return date.strftime(fmt)
    
    def generate_index(self) -> str:
        """生成首页"""
        base_template = self.load_template('base.html')
        index_template = self.load_template('index.html')
        
        # 生成时间轴 HTML
        timeline_html = self._generate_timeline()
        
        # 渲染首页内容
        index_content = self.render_template(
            index_template,
            timeline=timeline_html,
            post_count=str(len(self.posts))
        )
        
        # 渲染完整页面
        full_html = self.render_template(
            base_template,
            title=self.config.get('title', 'Munin Journal'),
            content=index_content,
            body_class='page-index',
            base_path=''
        )
        
        return full_html
    
    def _generate_timeline(self) -> str:
        """生成时间轴 HTML"""
        if not self.posts:
            return '<div class="empty-state"><p>还没有日记，开始写第一篇吧！</p></div>'
        
        items = []
        current_year = None
        
        for i, post in enumerate(self.posts):
            year = post.date.year
            
            # 年份标记
            if year != current_year:
                items.append(f'''
                <div class="timeline-year">
                    <span class="year-label">{year}</span>
                </div>
                ''')
                current_year = year
            
            # 奇偶位置（左/右）
            position = 'left' if i % 2 == 0 else 'right'
            
            # 标签 HTML
            tags_html = ''
            if post.tags:
                tags_html = '\n'.join([
                    f'<span class="tag">{tag}</span>'
                    for tag in post.tags[:3]  # 最多显示 3 个标签
                ])
            
            item_html = f'''
            <div class="timeline-item {position}" data-date="{post.date.isoformat()}">
                <div class="timeline-dot"></div>
                <article class="timeline-card">
                    <a href="posts/{post.slug}.html" class="card-link">
                        <header class="card-header">
                            <time class="card-date" datetime="{post.date.isoformat()}">
                                {self.format_date(post.date)}
                            </time>
                            <h2 class="card-title">{post.title}</h2>
                        </header>
                        <div class="card-excerpt">
                            <p>{post.excerpt}</p>
                        </div>
                        <footer class="card-footer">
                            <div class="card-tags">
                                {tags_html}
                            </div>
                            <span class="read-more">阅读更多 →</span>
                        </footer>
                    </a>
                </article>
            </div>
            '''
            items.append(item_html)
        
        return '\n'.join(items)
    
    def generate_post_page(self, post: Post) -> str:
        """生成单篇文章页面"""
        base_template = self.load_template('base.html')
        post_template = self.load_template('post.html')
        
        # 标签 HTML
        tags_html = ''
        if post.tags:
            tags_html = '\n'.join([
                f'<span class="tag">{tag}</span>'
                for tag in post.tags
            ])
        
        # 上一篇/下一篇导航
        post_index = self.posts.index(post)
        prev_link = ''
        next_link = ''
        
        if post_index < len(self.posts) - 1:
            prev_post = self.posts[post_index + 1]
            prev_link = f'''<div class="nav-item nav-prev-wrapper">
                    <span class="nav-label">← 上一篇</span>
                    <a href="{prev_post.slug}.html" class="nav-prev">{prev_post.title}</a>
                </div>'''
        
        if post_index > 0:
            next_post = self.posts[post_index - 1]
            next_link = f'''<div class="nav-item nav-next-wrapper">
                    <span class="nav-label">下一篇 →</span>
                    <a href="{next_post.slug}.html" class="nav-next">{next_post.title}</a>
                </div>'''
        
        # 渲染文章内容
        post_content = self.render_template(
            post_template,
            title=post.title,
            date=self.format_date(post.date),
            datetime=post.date.isoformat(),
            content=post.content,
            tags=tags_html,
            prev_link=prev_link,
            next_link=next_link
        )
        
        # 渲染完整页面
        page_title = f"{post.title} - {self.config.get('title', 'Munin Journal')}"
        full_html = self.render_template(
            base_template,
            title=page_title,
            content=post_content,
            body_class='page-post',
            base_path='../'
        )
        
        return full_html
    
    def copy_assets(self):
        """复制静态资源"""
        assets_src = self.base_dir / 'assets'
        assets_dst = self.output_dir / 'assets'
        
        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)
            print(f"已复制静态资源: {assets_dst}")
    
    def copy_images(self):
        """复制图片"""
        images_src = self.content_dir / 'images'
        images_dst = self.output_dir / 'images'
        
        if images_src.exists():
            if images_dst.exists():
                shutil.rmtree(images_dst)
            shutil.copytree(images_src, images_dst)
            print(f"已复制图片: {images_dst}")
    
    def build(self):
        """执行完整构建"""
        print("=" * 50)
        print("Munin Journal - 开始构建")
        print("=" * 50)
        
        # 清理输出目录
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        
        # 加载文章
        print("\n📄 加载文章...")
        self.posts = self.load_posts()
        print(f"  找到 {len(self.posts)} 篇文章")
        
        # 生成首页
        print("\n🏠 生成首页...")
        index_html = self.generate_index()
        with open(self.output_dir / 'index.html', 'w', encoding='utf-8') as f:
            f.write(index_html)
        print("  已生成: index.html")
        
        # 生成文章页面
        print("\n📝 生成文章页面...")
        posts_dir = self.output_dir / 'posts'
        posts_dir.mkdir()
        
        for post in self.posts:
            post_html = self.generate_post_page(post)
            post_path = posts_dir / f"{post.slug}.html"
            with open(post_path, 'w', encoding='utf-8') as f:
                f.write(post_html)
            print(f"  已生成: posts/{post.slug}.html")
        
        # 复制静态资源
        print("\n📦 复制静态资源...")
        self.copy_assets()
        self.copy_images()
        
        print("\n" + "=" * 50)
        print("✅ 构建完成!")
        print(f"输出目录: {self.output_dir}")
        print("=" * 50)


def main():
    """主函数"""
    import sys
    
    # 确定配置路径
    config_path = Path(__file__).parent / 'config.yml'
    
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}")
        sys.exit(1)
    
    # 加载配置
    config = Config(str(config_path))
    
    # 创建构建器并执行构建
    builder = SiteBuilder(config)
    builder.build()


if __name__ == '__main__':
    main()
