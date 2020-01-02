# Change Log

# 3.0.0

* Dropping support for Python 2
* Removing TornadoExecutor in favor of built in AsyncioExecutor
* Switching to native coroutines

# 2.5.1 

* Better naming for OpenCensus spans and signature caching

# 2.5.0

* Apollo Engine and Opencensus trace extensions

# 2.4.0

* Adding some tooling for building observability tools ported from apollo-tooling

# 2.3.0

* Fix for field resolvers in extension framework

# 2.2.0

* Added experimental extensions framework

## 2.1.0

* Upgraded to Graphene 2.1
* Allow users to provide their own GraphQLBackend implementation
* Use GraphQLBackend for document parsing
* Cache body and document parsing in case subclasses need their values for logic
* Remove the use of deprecated parameters names in GraphQL execute function
