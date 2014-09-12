Openstack Swift ContainerAlias Middleware
=========================================

``containeralias`` is a middleware which redirects requests to a different
container given by the ``x-container-meta-storage-path`` container metadata 
entry. The target container can also reside within another account.
Think of it like a symbolic link found in many file systems.

Additionally whenever a user sets an ACL the middleware tries to create an
alias container within the account granted access to. By doing this the user
will see the container in his account listing and can use the container just 
like his own containers.

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
    As stated earlier the middleware takes also care of creating the alias
    container whenever an ACL is set.

2.  Update static web objects without breaking links 
    
    Let's assume you have a container with a lot of static assets for a
    website: images, large downloads, Javascript/CSS files, you name it. Some
    day you need to move files or use another container or account.  This 
    might break existing links or make public known URLs unusable.  By 
    redirecting requests to the new container (or account) you can maintain 
    access at two known locations.

Current status
--------------
As of writing this post the swift-aclalias middleware lacks support for 
Keystone, but it is in the works already. 

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

2) Add a filter entry for containeralias to your proxy-server.conf and
   set auth_method either to tempauth, keystone or swauth. If you'r using
   a non-default reseller prefix you have to set this also.
  
    [filter:containeralias]
    use = egg:containeralias#containeralias
    auth_method = swauth
    #prefix = SHARED_
    #reseller_prefix = AUTH 

   If you are using keystone, you must also provide the authentication credentials of the keystone admin.

    [filter:containeralias]
    use = egg:containeralias#containeralias
    auth_method = keystone
    keystone_admin_user = admin
    keystone_admin_password = secret
    keystone_admin_tenant = admin
    keystone_admin_uri = http://localhost:35357/v2.0


3) Alter your proxy-server.conf pipeline and add containeralias after your
   authentication middleware.

    [pipeline:main]
    pipeline = catch_errors healthcheck cache tempauth containeralias proxy-server

4) Restart your proxy server: 

    swift-init proxy reload

Done!


Example use
-----------

Using a Swift all in one (SAIO) installation this will work as following:

1) Create target container with ACL for another account:

    swift -A http://127.0.0.1:8080/auth/v1.0 -U test:tester -K testing post -r test2:tester2 target_container

2) Upload some data to new container:
    
    swift -A http://127.0.0.1:8080/auth/v1.0 -U test:tester -K testing upload target_container testfile1
    
3) Accessing the new alias container will show/return objects from the original container:

    swift -A http://127.0.0.1:8080/auth/v1.0 -U test2:tester2 -K testing2 list 
    > SHARED_test_target_container

    swift -A http://127.0.0.1:8080/auth/v1.0 -U test2:tester2 -K testing2 list SHARED_test_target_container
    > testfile1
