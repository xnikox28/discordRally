# import importlib, pkgutil

# def setup_commands(bot):
#     package = __name__
#     for _, module_name, _ in pkgutil.iter_modules(__path__):
#         try:
#             module = importlib.import_module(f"{package}.{module_name}")
#             if hasattr(module, "setup"):
#                 module.setup(bot)
#                 print(f"✅ Comando cargado: {module_name}")
#             else:
#                 print(f"⚠️ {module_name} no define setup(bot)")
#         except Exception as e:
#             print(f"❌ Error cargando {module_name}: {e}")



# comandos/__init__.py
import importlib
import pkgutil
import inspect
import asyncio

def setup_commands(bot):
    package = __name__
    loop = asyncio.get_event_loop()
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        try:
            module = importlib.import_module(f"{package}.{module_name}")
            if hasattr(module, "setup"):
                ret = module.setup(bot)
                if inspect.isawaitable(ret):
                    loop.create_task(ret) # type: ignore
                print(f"✅ Comando cargado: {module_name}")
            else:
                print(f"⚠️ {module_name} no define setup(bot)")
        except Exception as e:
            print(f"❌ Error cargando {module_name}: {e}")
