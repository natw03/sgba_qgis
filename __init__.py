def classFactory(iface):
    from .sgba_plugin import SGBAPlugin
    return SGBAPlugin(iface)