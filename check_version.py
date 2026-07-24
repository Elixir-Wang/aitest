import pkg_resources
print("langchain version:", pkg_resources.get_distribution("langchain").version)
print("langgraph version:", pkg_resources.get_distribution("langgraph").version)
