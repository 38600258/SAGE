#!/bin/bash
# Hermes Kanban 多 Profile 环境配置脚本
# 用法: bash scripts/setup_profiles.sh
set -e

HERMES=${HERMES_BIN:-hermes}

echo "=== Hermes Kanban 环境配置 ==="

# 1. 检查 hermes 是否可用
if ! command -v $HERMES &> /dev/null; then
    echo "❌ hermes 命令不可用，请先安装 Hermes Agent"
    exit 1
fi
echo "✅ hermes: $(which $HERMES)"

# 2. 检查 coder profile 是否存在
if [ ! -d ~/.hermes/profiles/coder ]; then
    echo "⚠️  coder profile 不存在，创建中..."
    $HERMES profile create coder
fi
echo "✅ coder profile 就绪"

# 3. 创建 reviewer profile（从 coder clone，确保含 kanban-worker）
if [ ! -d ~/.hermes/profiles/reviewer ]; then
    echo "⚠️  reviewer profile 不存在，从 coder 克隆..."
    $HERMES profile create reviewer --clone --clone-from coder
fi
echo "✅ reviewer profile 就绪"

# 4. 自动配置 reviewer 模型和防止技能名冲突
echo ""
echo "=== 自动配置 YAML ==="

python3 << 'PYEOF'
import yaml
import os
from pathlib import Path

def patch_config(profile_name, is_reviewer=False):
    cfg_path = Path.home() / '.hermes' / 'profiles' / profile_name / 'config.yaml'
    if not cfg_path.exists():
        return
    
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}

    # 防止技能目录冲突（重要）
    cfg['external_dirs'] = []

    if is_reviewer:
        if 'model' not in cfg:
            cfg['model'] = {}
        cfg['model']['default'] = 'glm-5.1'
        cfg['model']['provider'] = 'custom'
        
        # 注入自定义提供商 (Volcano Engine GLM-5.1 示例)
        if 'custom_providers' not in cfg:
            cfg['custom_providers'] = []
            
        names = [p.get('name') for p in cfg.get('custom_providers', [])]
        if 'ark-review' not in names:
            cfg['custom_providers'].append({
                'name': 'ark-review',
                'base_url': 'https://ark.cn-beijing.volces.com/api/coding/v3',
                'api_key': os.environ.get('ARK_API_KEY', 'your-api-key-here'),
                'model': 'glm-5.1',
                'api_mode': 'chat_completions',
                'models': {'glm-5.1': {'context_length': 128000}}
            })

    with open(cfg_path, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
    print(f"✅ 已自动配置 {profile_name}/config.yaml")

patch_config('coder', is_reviewer=False)
patch_config('reviewer', is_reviewer=True)
PYEOF

# 5. 部署技能包
echo ""
echo "=== 部署技能包 ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$(dirname "$SCRIPT_DIR")/skills"

# coder 技能
for skill in dev-orchestrator dev-planner dev-coder dev-closer dev-doc-gardener; do
    target=~/.hermes/profiles/coder/skills/$skill
    if [ -d "$target" ]; then
        echo "  ↻ 更新 coder/$skill"
        rm -rf "$target"
    else
        echo "  + 新增 coder/$skill"
    fi
    cp -r "$SKILLS_DIR/$skill" "$target"
done

# reviewer 技能
for skill in dev-reviewer; do
    target=~/.hermes/profiles/reviewer/skills/$skill
    if [ -d "$target" ]; then
        echo "  ↻ 更新 reviewer/$skill"
        rm -rf "$target"
    else
        echo "  + 新增 reviewer/$skill"
    fi
    cp -r "$SKILLS_DIR/$skill" "$target"
done

echo "✅ 技能包部署完成"

# 6. 验证
echo ""
echo "=== 验证 ==="
echo "--- coder skills ---"
$HERMES -p coder skills list 2>&1 | grep -E 'dev-|kanban' || echo "  (无匹配)"
echo "--- reviewer skills ---"
$HERMES -p reviewer skills list 2>&1 | grep -E 'dev-|kanban' || echo "  (无匹配)"

echo ""
echo "=== 配置完成 ==="
echo "启动网关: hermes -p coder gateway run --replace"
echo "监控任务: hermes -p coder kanban list --tenant <project>"
