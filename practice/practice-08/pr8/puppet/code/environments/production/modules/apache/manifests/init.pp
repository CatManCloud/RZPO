class apache (
  String $docroot      = '/var/www/custom',
  String $server_admin = 'admin@example.com',
) {
  package { 'apache2':
    ensure => installed,
  }

  service { 'apache2':
    ensure   => running,
    enable   => true,
    provider => 'debian',
    require  => Package['apache2'],
  }

  file { '/var/www/html/index.html':
    content => '<html><body><h1>Deployed by Puppet</h1></body></html>',
    require => Package['apache2'],
  }

  # Кастомный DocumentRoot
  file { $docroot:
    ensure  => directory,
    require => Package['apache2'],
  }

  file { "${docroot}/index.html":
    content => "<html><body><h1>Custom DocumentRoot by Puppet (ERB)</h1></body></html>",
    require => File[$docroot],
  }

  # Конфиг VirtualHost из ERB-шаблона
  file { '/etc/apache2/sites-available/custom.conf':
    content => template('apache/vhost.conf.erb'),
    require => Package['apache2'],
  }

  exec { 'a2dissite 000-default':
    command => '/usr/sbin/a2dissite 000-default',
    onlyif  => '/usr/bin/test -L /etc/apache2/sites-enabled/000-default.conf',
    require => Package['apache2'],
    notify  => Service['apache2'],
  }

  exec { 'a2ensite custom':
    command => '/usr/sbin/a2ensite custom.conf',
    creates => '/etc/apache2/sites-enabled/custom.conf',
    require => File['/etc/apache2/sites-available/custom.conf'],
    notify  => Service['apache2'],
  }
}