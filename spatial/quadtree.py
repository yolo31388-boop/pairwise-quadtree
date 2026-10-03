"""四叉树空间划分"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )


@dataclass
class Point:
    x: float
    y: float
    data: any = None
    radius: float = 0.0


class QuadtreeNode:
    __slots__ = ("boundary", "capacity", "depth", "points", "children", "divided")

    def __init__(self, boundary: Rect, capacity: int = 4, depth: int = 0):
        self.boundary = boundary
        self.capacity = capacity
        self.depth = depth
        self.points: list[Point] = []
        self.children: list[Optional["QuadtreeNode"]] = [None, None, None, None]
        self.divided = False

    def reset(self, boundary: Rect, capacity: int, depth: int):
        self.boundary = boundary
        self.capacity = capacity
        self.depth = depth
        self.points.clear()
        self.children = [None, None, None, None]
        self.divided = False


class Quadtree:
    def __init__(self, boundary: Rect, capacity: int = 4, max_depth: int = 10):
        self.boundary = boundary
        self.capacity = capacity
        self.max_depth = max_depth
        self.root = QuadtreeNode(boundary, capacity)
        self._pool: list[QuadtreeNode] = []

    # ---------- 对象池 ----------

    def _acquire_node(self, boundary: Rect, capacity: int, depth: int) -> QuadtreeNode:
        """从对象池获取节点，池空时才新建，降低GC压力"""
        if self._pool:
            node = self._pool.pop()
            node.reset(boundary, capacity, depth)
            return node
        return QuadtreeNode(boundary, capacity, depth)

    def _release_node(self, node: QuadtreeNode):
        """递归回收子树节点到对象池"""
        if node.divided:
            for child in node.children:
                if child is not None:
                    self._release_node(child)
        node.reset(node.boundary, node.capacity, node.depth)
        self._pool.append(node)

    # ---------- 插入 ----------

    def insert(self, point: Point) -> bool:
        """插入点：边界检查 + 深度限制 + 对象池"""
        if not self.boundary.contains(point.x, point.y):
            return False
        return self._insert(self.root, point)

    def _quadrant(self, node: QuadtreeNode, x: float, y: float) -> Optional[int]:
        for i, child in enumerate(node.children):
            if child is not None and child.boundary.contains(x, y):
                return i
        return None

    def _insert(self, node: QuadtreeNode, point: Point) -> bool:
        if node.divided:
            idx = self._quadrant(node, point.x, point.y)
            if idx is None:
                node.points.append(point)
                return True
            return self._insert(node.children[idx], point)

        if len(node.points) < node.capacity or node.depth >= self.max_depth:
            node.points.append(point)
            return True

        # 叶子已满且未到最大深度：细分，已有点下沉到子节点，
        # 触发细分的点留在当前节点（归属当前区域）
        self._subdivide(node)
        kept = []
        for p in node.points:
            idx = self._quadrant(node, p.x, p.y)
            if idx is None:
                kept.append(p)
            else:
                self._insert(node.children[idx], p)
        kept.append(point)
        node.points = kept
        return True

    def _subdivide(self, node: QuadtreeNode):
        """细分节点（子节点从对象池获取）"""
        x, y, w, h = node.boundary.x, node.boundary.y, node.boundary.width, node.boundary.height
        hw, hh = w / 2, h / 2
        depth = node.depth + 1
        node.children[0] = self._acquire_node(Rect(x, y, hw, hh), node.capacity, depth)
        node.children[1] = self._acquire_node(Rect(x + hw, y, hw, hh), node.capacity, depth)
        node.children[2] = self._acquire_node(Rect(x, y + hh, hw, hh), node.capacity, depth)
        node.children[3] = self._acquire_node(Rect(x + hw, y + hh, hw, hh), node.capacity, depth)
        node.divided = True

    # ---------- 查询 ----------

    def query_range(self, range_rect: Rect) -> list[Point]:
        """范围查询：剪枝 + 检查子节点 + 去重"""
        result: list[Point] = []
        seen: set[int] = set()
        self._query(self.root, range_rect, result, seen)
        return result

    def _query(self, node: QuadtreeNode, range_rect: Rect, result: list, seen: set):
        # 剪枝：范围与节点不相交则跳过整棵子树
        if not node.boundary.intersects(range_rect):
            return
        if node.divided:
            # 内部节点的点归属整个区域，节点相交即作为候选返回
            for point in node.points:
                if id(point) not in seen:
                    seen.add(id(point))
                    result.append(point)
            for child in node.children:
                if child is not None:
                    self._query(child, range_rect, result, seen)
        else:
            for point in node.points:
                if id(point) not in seen and range_rect.contains(point.x, point.y):
                    seen.add(id(point))
                    result.append(point)

    # ---------- 删除 ----------

    def remove(self, point: Point) -> bool:
        """删除点：更新节点 + 空子节点合并 + 边界维护"""
        return self._remove(self.root, point)

    def _remove(self, node: QuadtreeNode, point: Point) -> bool:
        for i, p in enumerate(node.points):
            if p is point or (p.x == point.x and p.y == point.y):
                node.points.pop(i)
                return True
        if node.divided:
            idx = self._quadrant(node, point.x, point.y)
            candidates = [node.children[idx]] if idx is not None else list(node.children)
            for child in candidates:
                if child is not None and self._remove(child, point):
                    self._try_merge(node)
                    return True
        return False

    def _try_merge(self, node: QuadtreeNode):
        """4个子节点都是空叶子时合并回叶子节点，子节点回收进对象池"""
        if not node.divided:
            return
        for child in node.children:
            if child is None or child.divided or child.points:
                return
        for child in node.children:
            self._release_node(child)
        node.children = [None, None, None, None]
        node.divided = False

    # ---------- 重建 ----------

    def clear(self):
        """清空树，旧节点全部回收进对象池，避免内存翻倍"""
        if self.root.divided:
            for child in self.root.children:
                if child is not None:
                    self._release_node(child)
        self.root.reset(self.boundary, self.capacity, 0)

    def rebuild(self):
        """重建：先清理旧节点，再按Morton序平衡插入，避免退化成链表"""
        points = self.get_all_points()
        self.clear()
        points.sort(key=self._morton_key)
        for p in points:
            self.insert(p)

    def _morton_key(self, p: Point) -> int:
        bx, by = self.boundary.x, self.boundary.y
        bw = max(self.boundary.width, 1e-12)
        bh = max(self.boundary.height, 1e-12)
        nx = min(max((p.x - bx) / bw, 0.0), 1.0)
        ny = min(max((p.y - by) / bh, 0.0), 1.0)
        xi, yi = int(nx * 65535), int(ny * 65535)
        key = 0
        for i in range(16):
            key |= ((xi >> i) & 1) << (2 * i)
            key |= ((yi >> i) & 1) << (2 * i + 1)
        return key

    def update(self, point: Point, new_x: float, new_y: float) -> bool:
        """增量更新：只移动单个点，不重建整棵树"""
        if not self._remove(self.root, point):
            return False
        point.x, point.y = new_x, new_y
        if not self.boundary.contains(new_x, new_y):
            return False
        return self._insert(self.root, point)

    # ---------- 碰撞检测 ----------

    def check_collisions(
        self,
        radius: Optional[float] = None,
        callback: Optional[Callable[[Point, Point], None]] = None,
    ) -> list[tuple[Point, Point]]:
        """碰撞检测：宽相位(四叉树剪枝) + 窄相位(精确圆形/AABB) + 回调通知"""
        points = self.get_all_points()
        radii = [self._radius_of(p, radius) for p in points]
        max_reach = max(radii, default=0.0)
        max_reach += max(
            (max(getattr(p, "width", 0.0), getattr(p, "height", 0.0)) for p in points),
            default=0.0,
        )

        pairs: list[tuple[Point, Point]] = []
        seen: set[tuple[int, int]] = set()
        for i, p in enumerate(points):
            # 宽相位：用四叉树范围查询粗筛候选，不相交的直接跳过
            reach = radii[i] + max_reach
            candidates = self.query_range(
                Rect(p.x - reach, p.y - reach, 2 * reach, 2 * reach)
            )
            for q in candidates:
                if q is p:
                    continue
                key = (id(p), id(q)) if id(p) < id(q) else (id(q), id(p))
                if key in seen:
                    continue
                seen.add(key)
                # 窄相位：精确碰撞测试
                if self._narrow_phase(p, q, radius):
                    pairs.append((p, q))
                    if callback is not None:
                        callback(p, q)
        return pairs

    @staticmethod
    def _radius_of(p: Point, default: Optional[float]) -> float:
        if default is not None:
            return default
        return getattr(p, "radius", 0.0) or 0.0

    def _narrow_phase(self, a: Point, b: Point, default_radius: Optional[float]) -> bool:
        ra = self._radius_of(a, default_radius)
        rb = self._radius_of(b, default_radius)
        aw, ah = getattr(a, "width", 0.0), getattr(a, "height", 0.0)
        bw, bh = getattr(b, "width", 0.0), getattr(b, "height", 0.0)

        a_circle = ra > 0 or (aw == 0 and ah == 0)
        b_circle = rb > 0 or (bw == 0 and bh == 0)

        if a_circle and b_circle:
            # 圆形-圆形
            r = ra + rb
            if r == 0:
                return a.x == b.x and a.y == b.y
            return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < r * r
        if not a_circle and not b_circle:
            # AABB-AABB
            return not (
                a.x + aw < b.x or b.x + bw < a.x
                or a.y + ah < b.y or b.y + bh < a.y
            )
        # 圆形-AABB：最近点距离
        circle, rect = (a, b) if a_circle else (b, a)
        cr = ra if a_circle else rb
        rw = getattr(rect, "width", 0.0)
        rh = getattr(rect, "height", 0.0)
        cx = min(max(circle.x, rect.x), rect.x + rw)
        cy = min(max(circle.y, rect.y), rect.y + rh)
        return (circle.x - cx) ** 2 + (circle.y - cy) ** 2 < cr * cr

    # ---------- 遍历 ----------

    def get_all_points(self) -> list[Point]:
        """获取所有点"""
        result: list[Point] = []
        self._collect(self.root, result)
        return result

    def _collect(self, node: QuadtreeNode, result: list):
        result.extend(node.points)
        if node.divided:
            for child in node.children:
                if child is not None:
                    self._collect(child, result)
