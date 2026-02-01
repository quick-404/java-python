import heapq

# --- File: AStar.java ---

# package: com.thealgorithms.datastructures.graphs

# import: java.util.ArrayList

# import: java.util.Comparator

# import: java.util.List

# import: java.util.PriorityQueue

class AStar:
    """* AStar class implements the A* pathfinding algorithm to find the shortest path in a graph.
 * The graph is represented using an adjacency list, and the algorithm uses a heuristic to estimate
 * the cost to reach the destination node.
 * Time Complexity = O(E), where E is equal to the number of edges"""
    def __init__(self):
        pass
    @staticmethod
    def initializeGraph(graph, data):
        #  Initializes the graph with edges defined in the input data
        for i in range(0, len(data), 4):
            graph.addEdge(AStar.Edge(data[i], data[i + 1], data[i + 2]))
    @staticmethod
    def aStar(from_, to, graph, heuristic):
        """* Implements the A* pathfinding algorithm to find the shortest path from a start node to a destination node.
     *
     * @param from     the starting node
     * @param to       the destination node
     * @param graph    the graph representation of the problem
     * @param heuristic the heuristic estimates for each node
     * @return a PathAndDistance object containing the shortest path and its distance"""
        queue_key = lambda a: (a.getDistance() + a.getEstimated())
        queue = []
        heapq.heappush(queue, (queue_key(AStar.PathAndDistance(0, list([from_]), heuristic[from_])), AStar.PathAndDistance(0, list([from_]), heuristic[from_])))
        solutionFound = False
        currentData = AStar.PathAndDistance(-1, None, -1)
        while not (not queue) and not solutionFound:
            currentData = heapq.heappop(queue)[1]
            currentPosition = currentData.getPath()[len(currentData.getPath()) - 1]
            if currentPosition == to:
                solutionFound = True
            else:
                for edge in graph.getNeighbours(currentPosition):
                    if not edge.getTo() in currentData.getPath():
                        updatedPath = list(currentData.getPath())
                        updatedPath.append(edge.getTo())
                        heapq.heappush(queue, (queue_key(AStar.PathAndDistance(currentData.getDistance() + edge.getWeight(), updatedPath, heuristic[edge.getTo()])), AStar.PathAndDistance(currentData.getDistance() + edge.getWeight(), updatedPath, heuristic[edge.getTo()])))
        return currentData if (solutionFound) else AStar.PathAndDistance(-1, None, -1)

    class Graph:
        """* Represents a graph using an adjacency list."""
        def __init__(self, size):
            self.graph = list()
            for i in range(size):
                self.graph.append(list())
        def getNeighbours(self, from_):
            return self.graph[from_]
        def addEdge(self, edge):
            #  Add a bidirectional edge to the graph
            self.graph[edge.getFrom()].append(AStar.Edge(edge.getFrom(), edge.getTo(), edge.getWeight()))
            self.graph[edge.getTo()].append(AStar.Edge(edge.getTo(), edge.getFrom(), edge.getWeight()))

    class Edge:
        """* Represents an edge in the graph with a start node, end node, and weight."""
        def __init__(self, from_, to, weight):
            self.from_ = from_
            self.to = to
            self.weight = weight
        def getFrom(self):
            return self.from_
        def getTo(self):
            return self.to
        def getWeight(self):
            return self.weight

    class PathAndDistance:
        """* Contains information about the path and its total distance."""
        def __init__(self, distance, path, estimated):
            self.distance = distance
            self.path = path
            self.estimated = estimated
        def getDistance(self):
            return self.distance
        def getPath(self):
            return self.path
        def getEstimated(self):
            return self.estimated

if __name__ == "__main__":
    pass

# --- 转换测试报告 ---
# 转换效率: 0.918
# 可解析度: 1.000 (2/2)
# --- 报告结束 ---
