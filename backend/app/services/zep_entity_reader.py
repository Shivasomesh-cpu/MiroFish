"""
Zepå®žä½“è¯»å–ä¸Žè¿‡æ»¤æœåŠ¡
ä»ŽZepå›¾è°±ä¸­è¯»å–èŠ‚ç‚¹ï¼Œç­›é€‰å‡ºç¬¦åˆé¢„å®šä¹‰å®žä½“ç±»åž‹çš„èŠ‚ç‚¹
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('posiedon.zep_entity_reader')

# ç”¨äºŽæ³›åž‹è¿”å›žç±»åž‹
T = TypeVar('T')


@dataclass
class EntityNode:
    """å®žä½“èŠ‚ç‚¹æ•°æ®ç»“æž„"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # ç›¸å…³çš„è¾¹ä¿¡æ¯
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # ç›¸å…³çš„å…¶ä»–èŠ‚ç‚¹ä¿¡æ¯
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """èŽ·å–å®žä½“ç±»åž‹ï¼ˆæŽ’é™¤é»˜è®¤çš„Entityæ ‡ç­¾ï¼‰"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """è¿‡æ»¤åŽçš„å®žä½“é›†åˆ"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    Zepå®žä½“è¯»å–ä¸Žè¿‡æ»¤æœåŠ¡
    
    ä¸»è¦åŠŸèƒ½ï¼š
    1. ä»ŽZepå›¾è°±è¯»å–æ‰€æœ‰èŠ‚ç‚¹
    2. ç­›é€‰å‡ºç¬¦åˆé¢„å®šä¹‰å®žä½“ç±»åž‹çš„èŠ‚ç‚¹ï¼ˆLabelsä¸åªæ˜¯Entityçš„èŠ‚ç‚¹ï¼‰
    3. èŽ·å–æ¯ä¸ªå®žä½“çš„ç›¸å…³è¾¹å’Œå…³è”èŠ‚ç‚¹ä¿¡æ¯
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY æœªé…ç½®")
        
        self.client = Zep(api_key=self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        å¸¦é‡è¯•æœºåˆ¶çš„Zep APIè°ƒç”¨
        
        Args:
            func: è¦æ‰§è¡Œçš„å‡½æ•°ï¼ˆæ— å‚æ•°çš„lambdaæˆ–callableï¼‰
            operation_name: æ“ä½œåç§°ï¼Œç”¨äºŽæ—¥å¿—
            max_retries: æœ€å¤§é‡è¯•æ¬¡æ•°ï¼ˆé»˜è®¤3æ¬¡ï¼Œå³æœ€å¤šå°è¯•3æ¬¡ï¼‰
            initial_delay: åˆå§‹å»¶è¿Ÿç§’æ•°
            
        Returns:
            APIè°ƒç”¨ç»“æžœ
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} ç¬¬ {attempt + 1} æ¬¡å°è¯•å¤±è´¥: {str(e)[:100]}, "
                        f"{delay:.1f}ç§’åŽé‡è¯•..."
                    )
                    time.sleep(delay)
                    delay *= 2  # æŒ‡æ•°é€€é¿
                else:
                    logger.error(f"Zep {operation_name} åœ¨ {max_retries} æ¬¡å°è¯•åŽä»å¤±è´¥: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        èŽ·å–å›¾è°±çš„æ‰€æœ‰èŠ‚ç‚¹ï¼ˆåˆ†é¡µèŽ·å–ï¼‰

        Args:
            graph_id: å›¾è°±ID

        Returns:
            èŠ‚ç‚¹åˆ—è¡¨
        """
        logger.info(f"èŽ·å–å›¾è°± {graph_id} çš„æ‰€æœ‰èŠ‚ç‚¹...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"å…±èŽ·å– {len(nodes_data)} ä¸ªèŠ‚ç‚¹")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        èŽ·å–å›¾è°±çš„æ‰€æœ‰è¾¹ï¼ˆåˆ†é¡µèŽ·å–ï¼‰

        Args:
            graph_id: å›¾è°±ID

        Returns:
            è¾¹åˆ—è¡¨
        """
        logger.info(f"èŽ·å–å›¾è°± {graph_id} çš„æ‰€æœ‰è¾¹...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"å…±èŽ·å– {len(edges_data)} æ¡è¾¹")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        èŽ·å–æŒ‡å®šèŠ‚ç‚¹çš„æ‰€æœ‰ç›¸å…³è¾¹ï¼ˆå¸¦é‡è¯•æœºåˆ¶ï¼‰
        
        Args:
            node_uuid: èŠ‚ç‚¹UUID
            
        Returns:
            è¾¹åˆ—è¡¨
        """
        try:
            # ä½¿ç”¨é‡è¯•æœºåˆ¶è°ƒç”¨Zep API
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"èŽ·å–èŠ‚ç‚¹è¾¹(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f"èŽ·å–èŠ‚ç‚¹ {node_uuid} çš„è¾¹å¤±è´¥: {str(e)}")
            return []
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        ç­›é€‰å‡ºç¬¦åˆé¢„å®šä¹‰å®žä½“ç±»åž‹çš„èŠ‚ç‚¹
        
        ç­›é€‰é€»è¾‘ï¼š
        - å¦‚æžœèŠ‚ç‚¹çš„Labelsåªæœ‰ä¸€ä¸ª"Entity"ï¼Œè¯´æ˜Žè¿™ä¸ªå®žä½“ä¸ç¬¦åˆæˆ‘ä»¬é¢„å®šä¹‰çš„ç±»åž‹ï¼Œè·³è¿‡
        - å¦‚æžœèŠ‚ç‚¹çš„LabelsåŒ…å«é™¤"Entity"å’Œ"Node"ä¹‹å¤–çš„æ ‡ç­¾ï¼Œè¯´æ˜Žç¬¦åˆé¢„å®šä¹‰ç±»åž‹ï¼Œä¿ç•™
        
        Args:
            graph_id: å›¾è°±ID
            defined_entity_types: é¢„å®šä¹‰çš„å®žä½“ç±»åž‹åˆ—è¡¨ï¼ˆå¯é€‰ï¼Œå¦‚æžœæä¾›åˆ™åªä¿ç•™è¿™äº›ç±»åž‹ï¼‰
            enrich_with_edges: æ˜¯å¦èŽ·å–æ¯ä¸ªå®žä½“çš„ç›¸å…³è¾¹ä¿¡æ¯
            
        Returns:
            FilteredEntities: è¿‡æ»¤åŽçš„å®žä½“é›†åˆ
        """
        logger.info(f"å¼€å§‹ç­›é€‰å›¾è°± {graph_id} çš„å®žä½“...")
        
        # èŽ·å–æ‰€æœ‰èŠ‚ç‚¹
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        # èŽ·å–æ‰€æœ‰è¾¹ï¼ˆç”¨äºŽåŽç»­å…³è”æŸ¥æ‰¾ï¼‰
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        # æž„å»ºèŠ‚ç‚¹UUIDåˆ°èŠ‚ç‚¹æ•°æ®çš„æ˜ å°„
        node_map = {n["uuid"]: n for n in all_nodes}
        
        # ç­›é€‰ç¬¦åˆæ¡ä»¶çš„å®žä½“
        filtered_entities = []
        entity_types_found = set()
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
            # ç­›é€‰é€»è¾‘ï¼šLabelså¿…é¡»åŒ…å«é™¤"Entity"å’Œ"Node"ä¹‹å¤–çš„æ ‡ç­¾
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]
            
            if not custom_labels:
                # åªæœ‰é»˜è®¤æ ‡ç­¾ï¼Œè·³è¿‡
                continue
            
            # å¦‚æžœæŒ‡å®šäº†é¢„å®šä¹‰ç±»åž‹ï¼Œæ£€æŸ¥æ˜¯å¦åŒ¹é…
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]
            
            entity_types_found.add(entity_type)
            
            # åˆ›å»ºå®žä½“èŠ‚ç‚¹å¯¹è±¡
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )
            
            # èŽ·å–ç›¸å…³è¾¹å’ŒèŠ‚ç‚¹
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                # èŽ·å–å…³è”èŠ‚ç‚¹çš„åŸºæœ¬ä¿¡æ¯
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)
        
        logger.info(f"ç­›é€‰å®Œæˆ: æ€»èŠ‚ç‚¹ {total_count}, ç¬¦åˆæ¡ä»¶ {len(filtered_entities)}, "
                   f"å®žä½“ç±»åž‹: {entity_types_found}")
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        èŽ·å–å•ä¸ªå®žä½“åŠå…¶å®Œæ•´ä¸Šä¸‹æ–‡ï¼ˆè¾¹å’Œå…³è”èŠ‚ç‚¹ï¼Œå¸¦é‡è¯•æœºåˆ¶ï¼‰
        
        Args:
            graph_id: å›¾è°±ID
            entity_uuid: å®žä½“UUID
            
        Returns:
            EntityNodeæˆ–None
        """
        try:
            # ä½¿ç”¨é‡è¯•æœºåˆ¶èŽ·å–èŠ‚ç‚¹
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"èŽ·å–èŠ‚ç‚¹è¯¦æƒ…(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # èŽ·å–èŠ‚ç‚¹çš„è¾¹
            edges = self.get_node_edges(entity_uuid)
            
            # èŽ·å–æ‰€æœ‰èŠ‚ç‚¹ç”¨äºŽå…³è”æŸ¥æ‰¾
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
            # å¤„ç†ç›¸å…³è¾¹å’ŒèŠ‚ç‚¹
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # èŽ·å–å…³è”èŠ‚ç‚¹ä¿¡æ¯
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f"èŽ·å–å®žä½“ {entity_uuid} å¤±è´¥: {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        èŽ·å–æŒ‡å®šç±»åž‹çš„æ‰€æœ‰å®žä½“
        
        Args:
            graph_id: å›¾è°±ID
            entity_type: å®žä½“ç±»åž‹ï¼ˆå¦‚ "Student", "PublicFigure" ç­‰ï¼‰
            enrich_with_edges: æ˜¯å¦èŽ·å–ç›¸å…³è¾¹ä¿¡æ¯
            
        Returns:
            å®žä½“åˆ—è¡¨
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities


