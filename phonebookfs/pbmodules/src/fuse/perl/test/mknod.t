#!/usr/bin/perl
use test::helper qw($_real $_point);
use Test::More;
plan tests => 24;
my (@stat);
chdir($_point);
ok(!(system("touch reg"      )>>8),"create normal file");
ok(!(system("mknod chr c 2 3")>>8),"create chrdev");
ok(!(system("mknod blk b 2 3")>>8),"create blkdev");
ok(!(system("mknod fifo p"   )>>8),"create fifo");
chdir($_real);
ok(-e "reg" ,"normal file exists");
ok(-e "chr" ,"chrdev exists");
ok(-e "blk" ,"blkdev exists");
ok(-e "fifo","fifo exists");
ok(-f "reg" ,"normal file is normal file");
ok(-c "chr" ,"chrdev is chrdev");
ok(-b "blk" ,"blkdev is blkdev");
ok(-p "fifo","fifo is fifo");
@stat = stat("chr");
is($stat[6],3+(2<<8),"chrdev has right major,minor");
@stat = stat("blk");
is($stat[6],3+(2<<8),"blkdev has right major,minor");
chdir($_point);
ok(-e "reg" ,"normal file exists");
ok(-e "chr" ,"chrdev exists");
ok(-e "blk" ,"blkdev exists");
ok(-e "fifo","fifo exists");
ok(-f "reg" ,"normal file is normal file");
ok(-c "chr" ,"chrdev is chrdev");
ok(-b "blk" ,"blkdev is blkdev");
ok(-p "fifo","fifo is fifo");
@stat = stat("chr");
is($stat[6],3+(2<<8),"chrdev has right major,minor");
@stat = stat("blk");
is($stat[6],3+(2<<8),"blkdev has right major,minor");
map { unlink } qw(reg chr blk fifo);
