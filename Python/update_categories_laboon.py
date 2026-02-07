#!/usr/bin/env python3
"""
Script para actualizar las categorías en la base de datos laboon.db
basándose en las nuevas categorías definidas en signatures.json
"""

import sys
import os
import pickle
import sqlite3
from pathlib import Path

# Add the Python directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from modules.db_manager import DB_Manager
from modules.helpers import default_creds_category

def load_source_code_if_needed(http_object, source_dir):
    """
    Carga el código fuente HTML desde el archivo si no está en el objeto.
    
    Args:
        http_object: Objeto HTTPTableObject
        source_dir: Directorio donde están los archivos fuente
        
    Returns:
        bool: True si se cargó el código fuente, False si no
    """
    # Si ya tiene source_code, no hacer nada
    if http_object.source_code is not None:
        return False
    
    # Intentar cargar desde el archivo fuente
    if http_object.source_path and os.path.exists(http_object.source_path):
        try:
            with open(http_object.source_path, 'r', encoding='utf-8', errors='ignore') as f:
                http_object.source_code = f.read()
            return True
        except Exception as e:
            print(f"    [!] Error cargando source_code desde {http_object.source_path}: {e}")
            return False
    
    # Intentar construir la ruta del archivo fuente basándose en remote_system
    if http_object.remote_system:
        # Convertir URL a nombre de archivo
        url_parts = http_object.remote_system.replace('http://', '').replace('https://', '')
        url_parts = url_parts.replace(':', '.')
        source_file = os.path.join(source_dir, f"http.{url_parts}.txt")
        
        if os.path.exists(source_file):
            try:
                with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
                    http_object.source_code = f.read()
                return True
            except Exception as e:
                print(f"    [!] Error cargando source_code desde {source_file}: {e}")
                return False
    
    return False

def update_categories_in_database(db_path):
    """
    Recategoriza todos los objetos HTTP en la base de datos y guarda los cambios.
    
    Args:
        db_path (str): Ruta a la base de datos SQLite
    """
    if not os.path.isfile(db_path):
        print(f"[!] Error: No se encontró la base de datos en {db_path}")
        return False
    
    print(f"[*] Abriendo base de datos: {db_path}")
    dbm = DB_Manager(db_path)
    dbm.open_connection()
    
    # Determinar el directorio de archivos fuente
    db_dir = os.path.dirname(db_path)
    source_dir = os.path.join(db_dir, 'source')
    
    # Obtener todos los objetos HTTP completos
    c = dbm.connection.cursor()
    rows = c.execute("SELECT * FROM http WHERE complete=1").fetchall()
    total = len(rows)
    
    if total == 0:
        print("[!] No se encontraron objetos HTTP completos en la base de datos")
        c.close()
        return False
    
    print(f"[*] Encontrados {total} objetos HTTP para recategorizar")
    if os.path.exists(source_dir):
        print(f"[*] Directorio de archivos fuente: {source_dir}")
    print("[*] Iniciando recategorización...\n")
    
    updated_count = 0
    changes = []
    counter = 0
    source_loaded_count = 0
    
    for row in rows:
        # Deserializar el objeto
        o = pickle.loads(row['object'])
        
        # Cargar datos UA si existen
        uadat = c.execute("SELECT * FROM ua WHERE parent_id=?", (o.id,)).fetchall()
        for ua in uadat:
            uao = pickle.loads(ua['object'])
            if uao is not None:
                o.add_ua_data(uao)
        
        # Intentar cargar source_code si no está disponible
        if o.source_code is None and os.path.exists(source_dir):
            if load_source_code_if_needed(o, source_dir):
                source_loaded_count += 1
        
        # Guardar la categoría anterior
        old_category = o.category
        old_url = o.remote_system
        
        # Recategorizar usando las nuevas firmas
        # Recategorizar todos, incluso los que tienen categoría
        o = default_creds_category(o)
        
        new_category = o.category
        
        # Si la categoría cambió, actualizar en la base de datos
        if old_category != new_category:
            # Serializar y actualizar en la base de datos
            o_serialized = sqlite3.Binary(pickle.dumps(o, protocol=2))
            c.execute("UPDATE http SET object=?, complete=? WHERE id=?", 
                     (o_serialized, True, o.id))
            
            changes.append({
                'url': old_url,
                'old': old_category or 'None',
                'new': new_category or 'None'
            })
            
            updated_count += 1
            print(f"  [{counter+1}/{total}] {old_url}")
            print(f"    Categoría: {old_category or 'None'} -> {new_category or 'None'}")
        
        counter += 1
        
        # Mostrar progreso cada 10 objetos
        if counter % 10 == 0:
            print(f"[*] Procesados {counter}/{total} objetos...")
    
    # Confirmar cambios
    dbm.connection.commit()
    c.close()
    
    print(f"\n[*] Recategorización completada!")
    print(f"[*] Total de objetos procesados: {total}")
    print(f"[*] Categorías actualizadas: {updated_count}")
    if source_loaded_count > 0:
        print(f"[*] Archivos fuente cargados: {source_loaded_count}")
    
    if changes:
        print(f"\n[*] Resumen de cambios:")
        for change in changes[:20]:  # Mostrar primeros 20 cambios
            print(f"  - {change['url']}: {change['old']} -> {change['new']}")
        if len(changes) > 20:
            print(f"  ... y {len(changes) - 20} cambios más")
    
    return True

if __name__ == "__main__":
    # Ruta a la base de datos laboon
    laboon_db = Path(__file__).parent.parent / "eyewitness_projects" / "laboon" / "laboon.db"
    
    if len(sys.argv) > 1:
        laboon_db = Path(sys.argv[1])
    
    if not laboon_db.exists():
        print(f"[!] Error: No se encontró la base de datos en {laboon_db}")
        print("[*] Uso: python update_categories_laboon.py [ruta_a_base_de_datos]")
        sys.exit(1)
    
    print("=" * 70)
    print("Script de Actualización de Categorías - EyeWitness")
    print("=" * 70)
    print()
    
    success = update_categories_in_database(str(laboon_db))
    
    if success:
        print("\n[+] ¡Actualización completada exitosamente!")
    else:
        print("\n[!] La actualización falló")
        sys.exit(1)

