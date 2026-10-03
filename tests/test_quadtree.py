"""四叉树测试"""
import pytest
from spatial.quadtree import Quadtree, Rect, Point


class TestInsert:
    def test_insert_outside_boundary(self):
        """边界外的点不应被插入"""
        qt = Quadtree(Rect(0, 0, 100, 100))
        result = qt.insert(Point(200, 200))
        assert result is False
        assert len(qt.get_all_points()) == 0

    def test_insert_correct_quadrant(self):
        """点应插入正确的象限"""
        qt = Quadtree(Rect(0, 0, 100, 100), capacity=1)
        # 插入5个点触发细分
        qt.insert(Point(10, 10))   # 左上
        qt.insert(Point(60, 10))   # 右上
        qt.insert(Point(10, 60))   # 左下
        qt.insert(Point(60, 60))   # 右下
        qt.insert(Point(30, 30))   # 左上

        # 查询左上区域应返回3个点
        result = qt.query_range(Rect(0, 0, 50, 50))
        assert len(result) == 3

    def test_max_depth(self):
        """超过最大深度时应停止细分"""
        qt = Quadtree(Rect(0, 0, 100, 100), capacity=1, max_depth=2)
        # 插入很多点在同一位置
        for i in range(20):
            qt.insert(Point(10 + i * 0.1, 10 + i * 0.1))
        # 不应该栈溢出，所有点都应被插入
        assert len(qt.get_all_points()) == 20


class TestQuery:
    def test_query_range(self):
        """范围查询应返回正确的点"""
        qt = Quadtree(Rect(0, 0, 100, 100))
        qt.insert(Point(10, 10))
        qt.insert(Point(50, 50))
        qt.insert(Point(90, 90))

        result = qt.query_range(Rect(0, 0, 60, 60))
        assert len(result) == 2
        assert any(p.x == 10 for p in result)
        assert any(p.x == 50 for p in result)

    def test_query_no_intersection(self):
        """不相交的范围应返回空"""
        qt = Quadtree(Rect(0, 0, 100, 100))
        qt.insert(Point(10, 10))
        result = qt.query_range(Rect(200, 200, 50, 50))
        assert len(result) == 0

    def test_query_deduplicate(self):
        """跨节点的点不应被重复返回"""
        qt = Quadtree(Rect(0, 0, 100, 100), capacity=1)
        # 插入点在边界附近
        for i in range(10):
            qt.insert(Point(50 + i * 0.01, 50 + i * 0.01))
        result = qt.query_range(Rect(0, 0, 100, 100))
        assert len(result) == 10


class TestRemove:
    def test_remove_point(self):
        """删除点后查询不应返回该点"""
        qt = Quadtree(Rect(0, 0, 100, 100))
        p = Point(10, 10)
        qt.insert(p)
        assert len(qt.get_all_points()) == 1
        qt.remove(p)
        assert len(qt.get_all_points()) == 0

    def test_remove_nonexistent(self):
        """删除不存在的点应返回False"""
        qt = Quadtree(Rect(0, 0, 100, 100))
        result = qt.remove(Point(999, 999))
        assert result is False
