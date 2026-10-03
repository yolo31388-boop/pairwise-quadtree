"""四叉树空间划分 - 存在bug"""
from dataclasses import dataclass, field
from typing import Optional


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


class QuadtreeNode:
    def __init__(self, boundary: Rect, capacity: int = 4, depth: int = 0):
        self.boundary = boundary
        self.capacity = capacity
        self.depth = depth
        self.points: list[Point] = []
        self.children: list[Optional["QuadtreeNode"]] = [None, None, None, None]
        self.divided = False


class Quadtree:
    def __init__(self, boundary: Rect, capacity: int = 4, max_depth: int = 10):
        self.root = QuadtreeNode(boundary, capacity)
        self.max_depth = max_depth

    def insert(self, point: Point) -> bool:
        """插入点 - BUG: 不检查边界"""
        # BUG: 不检查点是否在边界内
        return self._insert(self.root, point)

    def _insert(self, node: QuadtreeNode, point: Point) -> bool:
        # BUG: 不检查边界
        if len(node.points) < node.capacity or node.depth >= self.max_depth:
            node.points.append(point)
            return True
        if not node.divided:
            self._subdivide(node)
        # BUG: 不检查点在哪个子节点，直接插入第一个
        return self._insert(node.children[0], point)

    def _subdivide(self, node: QuadtreeNode):
        """细分节点"""
        x, y, w, h = node.boundary.x, node.boundary.y, node.boundary.width, node.boundary.height
        hw, hh = w / 2, h / 2
        node.children[0] = QuadtreeNode(Rect(x, y, hw, hh), node.capacity, node.depth + 1)
        node.children[1] = QuadtreeNode(Rect(x + hw, y, hw, hh), node.capacity, node.depth + 1)
        node.children[2] = QuadtreeNode(Rect(x, y + hh, hw, hh), node.capacity, node.depth + 1)
        node.children[3] = QuadtreeNode(Rect(x + hw, y + hh, hw, hh), node.capacity, node.depth + 1)
        node.divided = True

    def query_range(self, range_rect: Rect) -> list[Point]:
        """范围查询 - BUG: 只检查当前节点不检查子节点"""
        result = []
        # BUG: 不做剪枝，不检查子节点
        self._query(self.root, range_rect, result)
        return result

    def _query(self, node: QuadtreeNode, range_rect: Rect, result: list):
        # BUG: 不做剪枝
        for point in node.points:
            if range_rect.contains(point.x, point.y):
                result.append(point)
        if node.divided:
            # BUG: 不检查子节点是否相交，全部遍历
            for child in node.children:
                if child:
                    self._query(child, range_rect, result)

    def remove(self, point: Point) -> bool:
        """删除点 - BUG: 不更新节点，不合并"""
        # BUG: 只删除点，不做节点合并
        return self._remove(self.root, point)

    def _remove(self, node: QuadtreeNode, point: Point) -> bool:
        for i, p in enumerate(node.points):
            if p.x == point.x and p.y == point.y:
                node.points.pop(i)
                return True
        if node.divided:
            for child in node.children:
                if child and self._remove(child, point):
                    return True
        return False

    def get_all_points(self) -> list[Point]:
        """获取所有点"""
        result = []
        self._collect(self.root, result)
        return result

    def _collect(self, node: QuadtreeNode, result: list):
        result.extend(node.points)
        if node.divided:
            for child in node.children:
                if child:
                    self._collect(child, result)
