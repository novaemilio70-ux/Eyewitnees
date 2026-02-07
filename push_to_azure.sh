#!/bin/bash
# Script para hacer push a Azure DevOps
# Uso: ./push_to_azure.sh

echo "Haciendo push a Azure DevOps..."
echo "Si te pide credenciales:"
echo "  Username: tu-email@ejemplo.com"
echo "  Password: tu-Personal-Access-Token"
echo ""

git push azure master

