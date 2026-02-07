# Guía para Enviar Código a Azure DevOps

## Opción 1: Agregar Azure DevOps como Remote Adicional

Si quieres mantener GitHub y agregar Azure DevOps:

```bash
# 1. Obtén la URL de tu repositorio en Azure DevOps
# Formato: https://dev.azure.com/{organizacion}/{proyecto}/_git/{repositorio}
# O: https://{organizacion}@dev.azure.com/{organizacion}/{proyecto}/_git/{repositorio}

# 2. Agrega Azure DevOps como un remote adicional
git remote add azure https://dev.azure.com/{organizacion}/{proyecto}/_git/{repositorio}

# 3. Verifica los remotes
git remote -v

# 4. Haz push a Azure DevOps
git push azure master
# O si tu rama se llama 'main':
git push azure master:main
```

## Opción 2: Cambiar el Remote Principal a Azure DevOps

Si quieres usar Azure DevOps como único remote:

```bash
# 1. Elimina el remote de GitHub (opcional, puedes mantenerlo)
# git remote remove origin

# 2. Agrega Azure DevOps como origin
git remote add origin https://dev.azure.com/{organizacion}/{proyecto}/_git/{repositorio}

# O si ya existe origin, cámbialo:
git remote set-url origin https://dev.azure.com/{organizacion}/{proyecto}/_git/{repositorio}

# 3. Haz push
git push -u origin master
```

## Opción 3: Usar SSH (Recomendado)

Si tienes SSH configurado en Azure DevOps:

```bash
# 1. Agrega el remote con SSH
git remote add azure git@ssh.dev.azure.com:v3/{organizacion}/{proyecto}/{repositorio}

# 2. Haz push
git push azure master
```

## Autenticación en Azure DevOps

### Con Personal Access Token (PAT)

1. Ve a Azure DevOps → User Settings → Personal Access Tokens
2. Crea un nuevo token con permisos de "Code (read & write)"
3. Usa el token como contraseña cuando Git te lo pida

```bash
# Cuando te pida credenciales:
# Username: {tu-email-o-usuario}
# Password: {tu-personal-access-token}
```

### Con SSH Keys

1. Genera una clave SSH si no tienes:
```bash
ssh-keygen -t rsa -b 4096 -C "tu-email@ejemplo.com"
```

2. Copia la clave pública:
```bash
cat ~/.ssh/id_rsa.pub
```

3. Agrega la clave en Azure DevOps:
   - Ve a User Settings → SSH Public Keys
   - Agrega tu clave pública

## Comandos Completos (Ejemplo)

```bash
# 1. Verificar que los cambios están commiteados
git log --oneline -1

# 2. Agregar remote de Azure DevOps
git remote add azure https://dev.azure.com/MiOrganizacion/MiProyecto/_git/EyeWitness

# 3. Autenticarse (si es necesario)
# Git te pedirá credenciales la primera vez

# 4. Hacer push
git push azure master

# Si necesitas forzar (no recomendado a menos que sea necesario):
# git push azure master --force
```

## Crear Pull Request en Azure DevOps

Después de hacer push:

1. Ve a tu repositorio en Azure DevOps
2. Haz clic en "Pull Requests"
3. Crea un nuevo Pull Request desde `master` hacia la rama principal
4. Revisa los cambios y completa el PR

## Verificar el Push

```bash
# Ver los remotes configurados
git remote -v

# Ver el último commit
git log --oneline -1

# Ver el estado
git status
```

## Troubleshooting

### Error: "remote: TF401019: The Git repository with name or identifier..."
- Verifica que el nombre del repositorio sea correcto
- Asegúrate de tener permisos en el proyecto

### Error: "Authentication failed"
- Verifica tu Personal Access Token
- Asegúrate de que el token tenga permisos de "Code (read & write)"
- Si usas SSH, verifica que la clave esté agregada en Azure DevOps

### Error: "branch 'master' has no upstream branch"
- Usa: `git push -u azure master` para establecer el upstream

### Cambiar el nombre de la rama
Si Azure DevOps usa `main` en lugar de `master`:

```bash
# Renombrar la rama local
git branch -m master main

# Push a Azure DevOps
git push -u azure main
```

