from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.task import Task
from app.schemas.task import TaskTreeNode

class WBSService:
    async def get_project_wbs_tree(self, db: AsyncSession, project_id: UUID) -> List[TaskTreeNode]:
        # Fetch all tasks of the project with children and dependencies preloaded
        result = await db.execute(
            select(Task)
            .where(Task.project_id == project_id)
            .options(
                selectinload(Task.children),
                selectinload(Task.dependencies)
            )
            .order_by(Task.sort_order)
        )
        tasks = result.scalars().all()
        
        # Build map of all tasks for quick access
        task_map = {t.id: t for t in tasks}
        
        # We need to construct the tree in memory and calculate rollup values recursively.
        roots = [t for t in tasks if t.parent_id is None or t.parent_id not in task_map]
        
        def build_tree_node(task: Task) -> TaskTreeNode:
            project_children = [c for c in task.children if c.id in task_map]
            project_children.sort(key=lambda x: x.sort_order)
            
            children_nodes = [build_tree_node(c) for c in project_children]
            is_summary = len(children_nodes) > 0
            
            if is_summary:
                planned_start = min(c.planned_start for c in children_nodes)
                planned_end = max(c.planned_end for c in children_nodes)
                estimated_hours = sum(c.estimated_hours for c in children_nodes)
                actual_hours = sum(c.actual_hours for c in children_nodes)
                
                # Get all leaf descendants
                def get_leaves(node: TaskTreeNode) -> List[TaskTreeNode]:
                    if not node.children:
                        return [node]
                    leaves = []
                    for c in node.children:
                        leaves.extend(get_leaves(c))
                    return leaves
                
                # Construct temporary node to extract leaves
                temp_node = TaskTreeNode(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    priority=task.priority,
                    assignee_type=task.assignee_type,
                    assignee_name=task.assignee_name,
                    planned_start=planned_start,
                    planned_end=planned_end,
                    actual_start=task.actual_start,
                    actual_end=task.actual_end,
                    progress=0,
                    delay_days=0,
                    project_id=task.project_id,
                    parent_id=task.parent_id,
                    node_type=task.node_type,
                    sort_order=task.sort_order,
                    estimated_hours=estimated_hours,
                    actual_hours=actual_hours,
                    is_summary=True,
                    children=children_nodes
                )
                leaf_descendants = get_leaves(temp_node)
                
                sum_est = sum(l.estimated_hours for l in leaf_descendants)
                if sum_est > 0:
                    progress = sum(l.progress * l.estimated_hours for l in leaf_descendants) / sum_est
                else:
                    if leaf_descendants:
                        progress = sum(l.progress for l in leaf_descendants) / len(leaf_descendants)
                    else:
                        progress = 0
                
                delay_days = max(c.delay_days for c in children_nodes)
                
                return TaskTreeNode(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    priority=task.priority,
                    assignee_type=task.assignee_type,
                    assignee_name=task.assignee_name,
                    planned_start=planned_start,
                    planned_end=planned_end,
                    actual_start=task.actual_start,
                    actual_end=task.actual_end,
                    progress=int(progress),
                    delay_days=delay_days,
                    project_id=task.project_id,
                    parent_id=task.parent_id,
                    node_type=task.node_type,
                    sort_order=task.sort_order,
                    estimated_hours=estimated_hours,
                    actual_hours=actual_hours,
                    is_summary=True,
                    children=children_nodes
                )
            else:
                # Leaf node
                return TaskTreeNode(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    priority=task.priority,
                    assignee_type=task.assignee_type,
                    assignee_name=task.assignee_name,
                    planned_start=task.planned_start,
                    planned_end=task.planned_end,
                    actual_start=task.actual_start,
                    actual_end=task.actual_end,
                    progress=task.progress,
                    delay_days=task.delay_days,
                    project_id=task.project_id,
                    parent_id=task.parent_id,
                    node_type=task.node_type,
                    sort_order=task.sort_order,
                    estimated_hours=task.estimated_hours,
                    actual_hours=task.actual_hours,
                    is_summary=False,
                    children=[]
                )
        
        return [build_tree_node(r) for r in roots]

wbs_service = WBSService()
