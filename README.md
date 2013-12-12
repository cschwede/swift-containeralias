Openstack Swift Alias Middleware
=========================================

``alias`` is a middleware which redirects requests to a different
container or object given by the ``x-(container|object)-meta-alias`` 
metadata entry. The target can also reside within another account.
Think of it like a symbolic link found in many file systems.

Use cases
---------

Possible use cases:

1.  Access container from another account
    
    To access a container from another account you need to use the storage URL
    of that account. In most cases this requires a direct access with HTTP
    requests, making it unusable for many client applications. By creating an
    alias container you simply access that container in your own account and
    the middleware redirects requests to the target container, making it much
    easier to use.

2.  Update static web objects without breaking links 
    
    Let's assume you have a container with a lot of static assets for a
    website: images, large downloads, Javascript/CSS files, you name it. Some
    day you need to move files or use another container or account.  This 
    might break existing links or make public known URLs unusable.  By 
    redirecting requests to the new container (or account) you can maintain 
    access at two known locations.

Constraint
----------

To prevent inaccessible objects only empty containers can be used as an alias.
Otherwise objects in this container would be invisible and inaccessible as long
as the container is an alias.

Drawback
--------

There is at least one drawback in using aliased containers: a container list or
HEAD request to an alias container will always report 0 objects. From a
technical viewpoint this is correct (albeit this might confuse users): objects
are saved only once and should not be counted twice. 

Quick Install
-------------

1) Install containeralias:

    git clone git://github.com/cschwede/swift-containeralias.git
    cd swift-containeralias
    sudo python setup.py install

2) Add a filter entry for containeralias to your proxy-server.conf:
  
    [filter:alias]
    use = egg:alias#alias

3) Alter your proxy-server.conf pipeline and add alias after your
   authentication middleware.

    [pipeline:main]
    pipeline = catch_errors healthcheck cache tempauth alias proxy-server

4) Restart your proxy server: 

    swift-init proxy reload

Done!
