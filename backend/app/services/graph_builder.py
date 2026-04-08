"""
å›¾è°±æž„å»ºæœåŠ¡
æŽ¥å£2ï¼šä½¿ç”¨Zep APIæž„å»ºStandalone Graph
"""

import os
import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from zep_cloud.client import Zep
from zep_cloud import EpisodeData, EntityEdgeSourceTarget

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from .text_processor import TextProcessor
from ..utils.locale import t, get_locale, set_locale


@dataclass
class GraphInfo:
    """å›¾è°±ä¿¡æ¯"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    å›¾è°±æž„å»ºæœåŠ¡
    è´Ÿè´£è°ƒç”¨Zep APIæž„å»ºçŸ¥è¯†å›¾è°±
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY æœªé…ç½®")
        
        self.client = Zep(api_key=self.api_key)
        self.task_manager = TaskManager()
    
    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "Posiedon Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        å¼‚æ­¥æž„å»ºå›¾è°±
        
        Args:
            text: è¾“å…¥æ–‡æœ¬
            ontology: æœ¬ä½“å®šä¹‰ï¼ˆæ¥è‡ªæŽ¥å£1çš„è¾“å‡ºï¼‰
            graph_name: å›¾è°±åç§°
            chunk_size: æ–‡æœ¬å—å¤§å°
            chunk_overlap: å—é‡å å¤§å°
            batch_size: æ¯æ‰¹å‘é€çš„å—æ•°é‡
            
        Returns:
            ä»»åŠ¡ID
        """
        # åˆ›å»ºä»»åŠ¡
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # åœ¨åŽå°çº¿ç¨‹ä¸­æ‰§è¡Œæž„å»º
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh'
    ):
        """å›¾è°±æž„å»ºå·¥ä½œçº¿ç¨‹"""
        set_locale(locale)
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph')
            )
            
            # 1. åˆ›å»ºå›¾è°±
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=t('progress.graphCreated', graphId=graph_id)
            )
            
            # 2. è®¾ç½®æœ¬ä½“
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message=t('progress.ontologySet')
            )
            
            # 3. æ–‡æœ¬åˆ†å—
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=t('progress.textSplit', count=total_chunks)
            )
            
            # 4. åˆ†æ‰¹å‘é€æ•°æ®
            episode_uuids = self.add_text_batches(
                graph_id, chunks, batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),  # 20-60%
                    message=msg
                )
            )
            
            # 5. ç­‰å¾…Zepå¤„ç†å®Œæˆ
            self.task_manager.update_task(
                task_id,
                progress=60,
                message=t('progress.waitingZepProcess')
            )
            
            self._wait_for_episodes(
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),  # 60-90%
                    message=msg
                )
            )
            
            # 6. èŽ·å–å›¾è°±ä¿¡æ¯
            self.task_manager.update_task(
                task_id,
                progress=90,
                message=t('progress.fetchingGraphInfo')
            )
            
            graph_info = self._get_graph_info(graph_id)
            
            # å®Œæˆ
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)
    
    def create_graph(self, name: str) -> str:
        """åˆ›å»ºZepå›¾è°±ï¼ˆå…¬å¼€æ–¹æ³•ï¼‰"""
        graph_id = f"posiedon_{uuid.uuid4().hex[:16]}"
        
        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="Posiedon Social Simulation Graph"
        )
        
        return graph_id
    
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """è®¾ç½®å›¾è°±æœ¬ä½“ï¼ˆå…¬å¼€æ–¹æ³•ï¼‰"""
        import warnings
        from typing import Optional
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel
        
        # æŠ‘åˆ¶ Pydantic v2 å…³äºŽ Field(default=None) çš„è­¦å‘Š
        # è¿™æ˜¯ Zep SDK è¦æ±‚çš„ç”¨æ³•ï¼Œè­¦å‘Šæ¥è‡ªåŠ¨æ€ç±»åˆ›å»ºï¼Œå¯ä»¥å®‰å…¨å¿½ç•¥
        warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
        
        # Zep ä¿ç•™åç§°ï¼Œä¸èƒ½ä½œä¸ºå±žæ€§å
        RESERVED_NAMES = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}
        
        def safe_attr_name(attr_name: str) -> str:
            """å°†ä¿ç•™åç§°è½¬æ¢ä¸ºå®‰å…¨åç§°"""
            if attr_name.lower() in RESERVED_NAMES:
                return f"entity_{attr_name}"
            return attr_name
        
        # åŠ¨æ€åˆ›å»ºå®žä½“ç±»åž‹
        entity_types = {}
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")
            
            # åˆ›å»ºå±žæ€§å­—å…¸å’Œç±»åž‹æ³¨è§£ï¼ˆPydantic v2 éœ€è¦ï¼‰
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in entity_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # ä½¿ç”¨å®‰å…¨åç§°
                attr_desc = attr_def.get("description", attr_name)
                # Zep API éœ€è¦ Field çš„ descriptionï¼Œè¿™æ˜¯å¿…éœ€çš„
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText]  # ç±»åž‹æ³¨è§£
            
            attrs["__annotations__"] = annotations
            
            # åŠ¨æ€åˆ›å»ºç±»
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class
        
        # åŠ¨æ€åˆ›å»ºè¾¹ç±»åž‹
        edge_definitions = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")
            
            # åˆ›å»ºå±žæ€§å­—å…¸å’Œç±»åž‹æ³¨è§£
            attrs = {"__doc__": description}
            annotations = {}
            
            for attr_def in edge_def.get("attributes", []):
                attr_name = safe_attr_name(attr_def["name"])  # ä½¿ç”¨å®‰å…¨åç§°
                attr_desc = attr_def.get("description", attr_name)
                # Zep API éœ€è¦ Field çš„ descriptionï¼Œè¿™æ˜¯å¿…éœ€çš„
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str]  # è¾¹å±žæ€§ç”¨strç±»åž‹
            
            attrs["__annotations__"] = annotations
            
            # åŠ¨æ€åˆ›å»ºç±»
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description
            
            # æž„å»ºsource_targets
            source_targets = []
            for st in edge_def.get("source_targets", []):
                source_targets.append(
                    EntityEdgeSourceTarget(
                        source=st.get("source", "Entity"),
                        target=st.get("target", "Entity")
                    )
                )
            
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)
        
        # è°ƒç”¨Zep APIè®¾ç½®æœ¬ä½“
        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=entity_types if entity_types else None,
                edges=edge_definitions if edge_definitions else None,
            )
    
    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """åˆ†æ‰¹æ·»åŠ æ–‡æœ¬åˆ°å›¾è°±ï¼Œè¿”å›žæ‰€æœ‰ episode çš„ uuid åˆ—è¡¨"""
        episode_uuids = []
        total_chunks = len(chunks)
        
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size
            
            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=len(batch_chunks)),
                    progress
                )
            
            # æž„å»ºepisodeæ•°æ®
            episodes = [
                EpisodeData(data=chunk, type="text")
                for chunk in batch_chunks
            ]
            
            # å‘é€åˆ°Zep
            try:
                batch_result = self.client.graph.add_batch(
                    graph_id=graph_id,
                    episodes=episodes
                )
                
                # æ”¶é›†è¿”å›žçš„ episode uuid
                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)
                
                # é¿å…è¯·æ±‚è¿‡å¿«
                time.sleep(1)
                
            except Exception as e:
                if progress_callback:
                    progress_callback(t('progress.batchFailed', batch=batch_num, error=str(e)), 0)
                raise
        
        return episode_uuids
    
    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """ç­‰å¾…æ‰€æœ‰ episode å¤„ç†å®Œæˆï¼ˆé€šè¿‡æŸ¥è¯¢æ¯ä¸ª episode çš„ processed çŠ¶æ€ï¼‰"""
        if not episode_uuids:
            if progress_callback:
                progress_callback(t('progress.noEpisodesWait'), 1.0)
            return
        
        start_time = time.time()
        pending_episodes = set(episode_uuids)
        completed_count = 0
        total_episodes = len(episode_uuids)
        
        if progress_callback:
            progress_callback(t('progress.waitingEpisodes', count=total_episodes), 0)
        
        while pending_episodes:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        t('progress.episodesTimeout', completed=completed_count, total=total_episodes),
                        completed_count / total_episodes
                    )
                break
            
            # æ£€æŸ¥æ¯ä¸ª episode çš„å¤„ç†çŠ¶æ€
            for ep_uuid in list(pending_episodes):
                try:
                    episode = self.client.graph.episode.get(uuid_=ep_uuid)
                    is_processed = getattr(episode, 'processed', False)
                    
                    if is_processed:
                        pending_episodes.remove(ep_uuid)
                        completed_count += 1
                        
                except Exception as e:
                    # å¿½ç•¥å•ä¸ªæŸ¥è¯¢é”™è¯¯ï¼Œç»§ç»­
                    pass
            
            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(
                    t('progress.zepProcessing', completed=completed_count, total=total_episodes, pending=len(pending_episodes), elapsed=elapsed),
                    completed_count / total_episodes if total_episodes > 0 else 0
                )
            
            if pending_episodes:
                time.sleep(3)  # æ¯3ç§’æ£€æŸ¥ä¸€æ¬¡
        
        if progress_callback:
            progress_callback(t('progress.processingComplete', completed=completed_count, total=total_episodes), 1.0)
    
    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """èŽ·å–å›¾è°±ä¿¡æ¯"""
        # èŽ·å–èŠ‚ç‚¹ï¼ˆåˆ†é¡µï¼‰
        nodes = fetch_all_nodes(self.client, graph_id)

        # èŽ·å–è¾¹ï¼ˆåˆ†é¡µï¼‰
        edges = fetch_all_edges(self.client, graph_id)

        # ç»Ÿè®¡å®žä½“ç±»åž‹
        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )
    
    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        èŽ·å–å®Œæ•´å›¾è°±æ•°æ®ï¼ˆåŒ…å«è¯¦ç»†ä¿¡æ¯ï¼‰
        
        Args:
            graph_id: å›¾è°±ID
            
        Returns:
            åŒ…å«nodeså’Œedgesçš„å­—å…¸ï¼ŒåŒ…æ‹¬æ—¶é—´ä¿¡æ¯ã€å±žæ€§ç­‰è¯¦ç»†æ•°æ®
        """
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        # åˆ›å»ºèŠ‚ç‚¹æ˜ å°„ç”¨äºŽèŽ·å–èŠ‚ç‚¹åç§°
        node_map = {}
        for node in nodes:
            node_map[node.uuid_] = node.name or ""
        
        nodes_data = []
        for node in nodes:
            # èŽ·å–åˆ›å»ºæ—¶é—´
            created_at = getattr(node, 'created_at', None)
            if created_at:
                created_at = str(created_at)
            
            nodes_data.append({
                "uuid": node.uuid_,
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
                "created_at": created_at,
            })
        
        edges_data = []
        for edge in edges:
            # èŽ·å–æ—¶é—´ä¿¡æ¯
            created_at = getattr(edge, 'created_at', None)
            valid_at = getattr(edge, 'valid_at', None)
            invalid_at = getattr(edge, 'invalid_at', None)
            expired_at = getattr(edge, 'expired_at', None)
            
            # èŽ·å– episodes
            episodes = getattr(edge, 'episodes', None) or getattr(edge, 'episode_ids', None)
            if episodes and not isinstance(episodes, list):
                episodes = [str(episodes)]
            elif episodes:
                episodes = [str(e) for e in episodes]
            
            # èŽ·å– fact_type
            fact_type = getattr(edge, 'fact_type', None) or edge.name or ""
            
            edges_data.append({
                "uuid": edge.uuid_,
                "name": edge.name or "",
                "fact": edge.fact or "",
                "fact_type": fact_type,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": edge.attributes or {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            })
        
        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }
    
    def delete_graph(self, graph_id: str):
        """åˆ é™¤å›¾è°±"""
        self.client.graph.delete(graph_id=graph_id)

