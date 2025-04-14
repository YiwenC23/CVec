import os
import json
import faiss
import hashlib
import numpy as np
from uuid import uuid4


# ToDo: add logic for adding multiple files with same embedding dimension (same length of embedding list). Do it by setting a initial dimension value, like dim=512; then, generate embedding list to match the dimension for each file.
class VectorDB:
    def __init__(self, dim: int=745):
        """
        self.metadata_map: {uuid: {filepath: ..., filename: ...}}
        self.id_map: {filepath: uuid}
        """
        self.dim = dim
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        self.metadata_map = {}
        self.id_map = {}
    
    
    #* Convert uuid string to int64
    def _uuid_to_int64(self, uuid_str: str) -> int:
        hash_bytes = hashlib.sha256(uuid_str.encode()).digest()[:8]
        return np.frombuffer(hash_bytes, dtype=np.int64)[0]
    
    
    #* Add a file to the vector database
    def add_file(self, filepath: str, embeddings: list[list[float]]):
        #? Check if the file already exists
        if filepath in self.id_map:
            print(f"File {filepath} already exists in the database")
            return
        
        #? Generate a unique uuid for the file and convert it to int64
        file_uuid = str(uuid4())
        
        faiss_ids = []
        for i in range(len(embeddings)):
            chunk_uuid = f"{file_uuid}_{i}"
            faiss_id = self._uuid_to_int64(chunk_uuid)
            faiss_ids.append(faiss_id)
        
        #? Add the vector values of the file to the database
        emb_array = np.array(embeddings, dtype=np.float32)
        self.index.add_with_ids(emb_array, np.array(faiss_ids))
        
        #? Add the metadata of the file
        self.metadata_map[file_uuid] = {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "chunk_count": len(embeddings)
        }
        self.id_map[filepath] = file_uuid
    
    
    #* Delete a file as well as it vector values
    def delete_file(self, filepath: str):
        if filepath not in self.id_map:
            return False
        
        file_uuid = self.id_map[filepath]
        chunk_count = self.metadata_map[file_uuid].get("chunk_count", 1)
        
        #? Delete all vector values for this file
        faiss_ids = []
        for i in range(chunk_count):
            chunk_uuid = f"{file_uuid}_{i}"
            faiss_id = self._uuid_to_int64(chunk_uuid)
            faiss_ids.append(faiss_id)
        
        #? Delete the vector values
        self.index.remove_ids(np.array(faiss_ids, dtype=np.int64))
        
        #? Clean the mappings
        del self.metadata_map[file_uuid]
        del self.id_map[filepath]
        
        return True
    
    
    #* Save the vector database
    def save(self, path: str):
        faiss.write_index(self.index, f"{path}/index.faiss")
        with open(f"{path}/mapping.json", "w") as f:
            json.dump({
                "metadata": self.metadata_map,
                "id_map": self.id_map
            }, f)
    
    
    #* Load the vector database
    @classmethod
    def load(cls, path: str, dim: int):
        db = cls(dim)
        db.index = faiss.read_index(f"{path}/index.faiss")
        with open(f"{path}/mapping.json", "r") as f:
            data = json.load(f)
            db.metadata_map = data["metadata"]
            db.id_map = data["id_map"]
        
        return db
    
    
    #* Search for similar vectors
    def search(self, query_vector, k=5):
        """
        Search for the k nearest neighbors to the query vector.
        
        Args:
            query_vector: The query vector to search for (numpy array)
            k: Number of nearest neighbors to return
        
        Returns:
            distances, indices: arrays of distances and indices of the nearest neighbors
        """
        #? Ensure query_vector is a 2D array with right dimension
        if len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)
            
        #? Check dimensions and reshape if needed
        if query_vector.shape[1] != self.dim:
            print(f"Warning: Query vector dimension ({query_vector.shape[1]}) doesn't match index dimension ({self.dim})")
            #? Handle dimension mismatch (truncate or pad)
            if query_vector.shape[1] > self.dim:
                query_vector = query_vector[:, :self.dim]
            else:
                padded = np.zeros((query_vector.shape[0], self.dim), dtype=np.float32)
                padded[:, :query_vector.shape[1]] = query_vector
                query_vector = padded
        
        #? Search the index
        distances, indices = self.index.search(query_vector.astype("float32"), k)
        
        return distances, indices