"""
Project-level Pages Service

管理项目级pages产物的读写和更新
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import yaml
import logging

logger = logging.getLogger(__name__)


class ProjectPagesService:
    """项目级Pages管理服务"""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        """
        初始化服务

        Args:
            project_id: 项目ID
            base_dir: 数据根目录，默认为 data/projects/{project_id}/page_exploration
        """
        self.project_id = project_id

        if base_dir is None:
            base_dir = Path("data/projects") / project_id / "page_exploration"

        self.base_dir = Path(base_dir)
        self.pages_dir = self.base_dir / "pages"
        self.cache_index_file = self.base_dir / "cache_index.yaml"

        # 确保目录存在
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        读取项目级页面产物

        Args:
            page_id: 页面ID，如 page-workspace-agents

        Returns:
            页面产物字典，不存在返回None
        """
        page_file = self.pages_dir / f"{page_id}.yaml"

        if not page_file.exists():
            logger.warning(f"Page not found: {page_id}")
            return None

        try:
            with open(page_file, 'r', encoding='utf-8') as f:
                page_data = yaml.safe_load(f)

            logger.debug(f"Loaded page: {page_id}")
            return page_data

        except Exception as e:
            logger.error(f"Failed to load page {page_id}: {e}")
            return None

    def save_page(
        self,
        page_id: str,
        page_data: Dict[str, Any],
        run_id: str,
        url: str,
        normalized_path: str,
        env: str = "test"
    ) -> bool:
        """
        保存或更新项目级页面产物

        Args:
            page_id: 页面ID
            page_data: 页面数据（包含states、elements等）
            run_id: 当前探索运行ID
            url: 页面URL
            normalized_path: 归一化路径
            env: 环境标识（prod/test/local）

        Returns:
            是否保存成功
        """
        resolved_page_id = self.find_page_by_path(normalized_path) if normalized_path else None
        resolved_page_id = resolved_page_id or page_id
        page_file = self.pages_dir / f"{resolved_page_id}.yaml"

        try:
            # 如果页面已存在，加载并合并env_urls
            if page_file.exists():
                existing_page = self.get_page(resolved_page_id)
                if existing_page:
                    # 保留已有的env_urls
                    env_urls = existing_page.get('page', {}).get('env_urls', {})
                    env_urls[env] = url
                else:
                    env_urls = {env: url}
            else:
                env_urls = {env: url}

            # 构建完整的页面产物
            full_page_data = {
                'page': {
                    'id': resolved_page_id,
                    'title': page_data.get('title', ''),
                    'normalized_path': normalized_path,
                    'structure_summary': page_data.get('structure_summary', ''),
                    'path_hash': self._generate_path_hash(normalized_path),
                    'env_urls': env_urls,
                    'last_explored': {
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'run_id': run_id
                    }
                },
                'states': page_data.get('states', []),
                'quality': page_data.get('quality', {}),
                'metadata': page_data.get('metadata', {})
            }

            # 写入文件
            with open(page_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    full_page_data,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False
                )

            logger.info(f"Saved page: {resolved_page_id} to {page_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save page {page_id}: {e}")
            return False

    def list_pages(self) -> List[Dict[str, Any]]:
        """
        列出所有项目级页面

        Returns:
            页面列表（简化信息）
        """
        pages = []

        for page_file in self.pages_dir.glob("*.yaml"):
            if page_file.name == "pages-index.yaml":
                continue

            try:
                with open(page_file, 'r', encoding='utf-8') as f:
                    page_data = yaml.safe_load(f)

                page_info = page_data.get('page', {})
                pages.append({
                    'page_id': page_info.get('id'),
                    'title': page_info.get('title'),
                    'normalized_path': page_info.get('normalized_path'),
                    'structure_summary': page_info.get('structure_summary'),
                    'last_explored': page_info.get('last_explored'),
                    'file': page_file.name
                })

            except Exception as e:
                logger.error(f"Failed to read page file {page_file}: {e}")

        return pages

    def find_page_by_path(self, normalized_path: str) -> Optional[str]:
        """
        根据归一化路径查找页面ID

        Args:
            normalized_path: 归一化路径

        Returns:
            页面ID，不存在返回None
        """
        # 先从缓存索引查找（性能更好）
        cache_entry = self.get_cache_entry(normalized_path)
        if cache_entry:
            return cache_entry['page_id']

        # 回退：遍历所有页面文件
        for page_file in self.pages_dir.glob("*.yaml"):
            if page_file.name == "pages-index.yaml":
                continue

            try:
                with open(page_file, 'r', encoding='utf-8') as f:
                    page_data = yaml.safe_load(f)

                if page_data.get('page', {}).get('normalized_path') == normalized_path:
                    return page_data['page']['id']

            except Exception as e:
                logger.error(f"Failed to read page file {page_file}: {e}")

        return None

    def find_element(
        self,
        page_id: str,
        element_name: str,
        state_id: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """
        在页面中查找元素

        Args:
            page_id: 页面ID
            element_name: 元素名称（如："创建智能体"）
            state_id: 状态ID（默认为"default"）

        Returns:
            元素数据，不存在返回None
        """
        page_data = self.get_page(page_id)
        if not page_data:
            return None

        # 查找指定状态
        for state in page_data.get('states', []):
            if state.get('id') == state_id:
                # 在该状态的元素中查找
                for element in state.get('elements', []):
                    if element.get('name') == element_name:
                        return element

        return None

    def get_cache_entry(self, normalized_path: str) -> Optional[Dict[str, Any]]:
        """
        从缓存索引查找页面

        Args:
            normalized_path: 归一化路径

        Returns:
            缓存条目，不存在返回None
        """
        cache_index = self._load_cache_index()

        for entry in cache_index.get('pages', []):
            if entry.get('normalized_path') == normalized_path:
                return entry

        return None

    def update_cache_index(
        self,
        normalized_path: str,
        page_id: str,
        run_id: str,
        page_signature: Dict[str, Any],
        env_urls: Dict[str, str]
    ) -> bool:
        """
        更新项目级缓存索引

        Args:
            normalized_path: 归一化路径
            page_id: 页面ID
            run_id: 当前运行ID
            page_signature: 页面签名（title, element_count等）
            env_urls: 环境URL映射

        Returns:
            是否更新成功
        """
        try:
            cache_index = self._load_cache_index()

            # 查找是否已存在
            existing_entry = None
            for i, entry in enumerate(cache_index['pages']):
                if entry['normalized_path'] == normalized_path:
                    existing_entry = i
                    break

            resolved_page_id = page_id
            if existing_entry is not None:
                resolved_page_id = cache_index['pages'][existing_entry].get('page_id') or page_id

            # 构建缓存条目
            cache_entry = {
                'normalized_path': normalized_path,
                'page_id': resolved_page_id,
                'path_hash': self._generate_path_hash(normalized_path),
                'page_file': f"pages/{resolved_page_id}.yaml",
                'last_explored_at': datetime.utcnow().isoformat() + 'Z',
                'last_run_id': run_id,
                'signature': page_signature,
                'env_urls': env_urls
            }

            # 更新或添加
            if existing_entry is not None:
                # 合并env_urls
                existing_urls = cache_index['pages'][existing_entry].get('env_urls', {})
                existing_urls.update(env_urls)
                cache_entry['env_urls'] = existing_urls

                cache_index['pages'][existing_entry] = cache_entry
                logger.info(f"Updated cache entry for {normalized_path}")
            else:
                cache_index['pages'].append(cache_entry)
                logger.info(f"Added cache entry for {normalized_path}")

            # 更新时间戳
            cache_index['updated_at'] = datetime.utcnow().isoformat() + 'Z'

            # 写回文件
            self._save_cache_index(cache_index)
            return True

        except Exception as e:
            logger.error(f"Failed to update cache index: {e}")
            return False

    def check_cache(self, normalized_path: str) -> Dict[str, Any]:
        """
        检查页面是否已探索（缓存检查）

        Args:
            normalized_path: 归一化路径

        Returns:
            {
                'cache_hit': bool,
                'page_id': str,
                'page_file': str,
                'last_explored_at': str
            }
        """
        entry = self.get_cache_entry(normalized_path)

        if entry:
            page_file = self.base_dir / entry['page_file']

            if page_file.exists():
                return {
                    'cache_hit': True,
                    'page_id': entry['page_id'],
                    'page_file': str(page_file),
                    'last_explored_at': entry['last_explored_at'],
                    'signature': entry.get('signature', {})
                }

        return {'cache_hit': False}

    def _load_cache_index(self) -> Dict[str, Any]:
        """加载项目级缓存索引"""
        if not self.cache_index_file.exists():
            # 初始化缓存索引
            return {
                'version': '1.0',
                'project_id': self.project_id,
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'pages': []
            }

        try:
            with open(self.cache_index_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load cache index: {e}")
            return {'pages': []}

    def _save_cache_index(self, cache_index: Dict[str, Any]) -> bool:
        """保存项目级缓存索引"""
        try:
            with open(self.cache_index_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    cache_index,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
            return False

    def _generate_path_hash(self, normalized_path: str) -> str:
        """生成路径哈希"""
        import hashlib
        hash_obj = hashlib.sha256(normalized_path.encode('utf-8'))
        return f"sha256-{hash_obj.hexdigest()[:16]}"
