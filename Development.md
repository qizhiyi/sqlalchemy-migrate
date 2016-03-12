More about development in README file found in repository.

# Code #

All code can be found in our [mercurial repository](http://code.google.com/p/sqlalchemy-migrate/source/checkout).

# Continuous Integration #

We have a [Jenkins CI](http://jenkins-ci.org/) instance at http://jenkins.gnuviech-server.de/job/sqlalchemy-migrate/

Automatic tests are run there for the following list of databases:

  * PostgreSQL 8.4.5
  * MySQL 5.1.49
  * sqlite 3.7.3
  * Firebird 2.5

with Python 2.4, 2.5, 2.6 and 2.7 combined with [SQLAlchemy](http://sqlalchemy.org) 0.5.8, 0.6.7 and 0.7.0.

# How can you help? #

We would appreciate help on

  * triaging and reproducing the bugs listed on our [issue tracker](http://code.google.com/p/sqlalchemy-migrate/issues/list)
  * patches for known issues
  * supporting other databases or improve support of the supported ones
  * improve documentation